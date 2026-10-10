import json
import logging
import shutil
import time
import zipfile
from pathlib import Path

import requests

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError, FileProcessingError, ConfigurationError, \
    PdfConversionError
from processor.import_processor.state import ImportGraphState

class NodePDFToMD(BaseNode):
    name = "node_pdf_to_md"
    def process(self,state: ImportGraphState):
        #步骤1
        pdf_path_obj, output_dir_obj = self._step_1_validate_paths(state)
        #步骤2
        zip_url = self._step_2_upload_and_poll(pdf_path_obj)
        #步骤3
        md_path = self._step_3_download_and_extract(zip_url,output_dir_obj,pdf_path_obj.stem)
        #步骤4
        with open(md_path,"r",encoding="utf-8") as f:
            md_content = f.read()
        #步骤5
        state["md_path"] = md_path
        state["md_content"] = md_content
        return state
    def _step_1_validate_paths(self, state: ImportGraphState):
        pdf_path = state.get("pdf_path")
        if not pdf_path:
            raise StateFieldError(field_name="pdf_path",expected_type=str)
        file_dir = state.get("file_dir")
        if not file_dir:
            raise StateFieldError(field_name="file_dir",expected_type=str)
        pdf_path_obj = Path(pdf_path)
        file_dir_obj = Path(file_dir)
        if not pdf_path_obj.exists():
            raise FileProcessingError(message = f"PDF文件{pdf_path_obj.name}不存在")
        if not file_dir_obj.exists():
            self.logger.info(f"输出目录不存在，自动创建：{file_dir_obj.absolute()}")
            file_dir_obj.mkdir(parents=True, exist_ok=True)
        return pdf_path_obj,file_dir_obj

    def _step_2_upload_and_poll(self,pdf_path_obj: Path):
        if not self.config.mineru_base_url:
            raise ConfigurationError("MinerU配置缺失：请在.env文件中正确配置MINERU_BASE_URL参数")
        if not self.config.mineru_api_token:
            raise ConfigurationError("MinerU配置缺失：请在.env文件中正确配置MINERU_API_TOKEN参数")
        token = self.config.mineru_api_token
        url = f"{self.config.mineru_base_url}/file-urls/batch"
        header = {
            "Content-Type":"application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "files":[
                {"name":pdf_path_obj.name}
            ],
            "model_version":"vlm"
        }
        response = requests.post(url,headers=header,json=data)
        if response.status_code != 200:
            if response.status_code in (401, 403):
                raise PdfConversionError(
                    'MinerU 鉴权失败（HTTP {}），MINERU_API_TOKEN 已失效或无效。'
                    '请登录 https://mineru.net 个人中心重新生成 API Token，'
                    '并更新 .env 中的 MINERU_API_TOKEN 后重启导入服务。'
                    '原始响应：{}'.format(response.status_code, response.text[:200])
                )
            raise PdfConversionError('获取上传链接失败，响应状态:{},响应结果:{}'.format(response.status_code,response))
        result = response.json()
        if result["code"] != 0 :
            raise PdfConversionError('获取上传链接失败，返回数据：{}'.format(result["msg"]))
        batch_id = result["data"]["batch_id"]
        urls = result["data"]["file_urls"]
        with open(pdf_path_obj,"rb") as f:
            res_upload = requests.put(urls[0],data = f)
            if res_upload.status_code != 200:
                raise PdfConversionError(f'{urls[0]}文件上传失败')
            self.logger.info('上传文件成功！')
        poll_url = f"{self.config.mineru_base_url}/extract-results/batch/{batch_id}"
        start_time = time.time()
        timeout_seconds = 600
        poll_interval = 3
        self.log_step(
            step_name = "轮询开始",
            message=f"轮询间隔：{poll_interval}s，超时时间：{timeout_seconds}s，batch_id:{batch_id}"
        )
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout_seconds:
                raise TimeoutError(f"[任务轮询]超时，已消耗时间：{int(elapsed_time)}s,batch_id:{batch_id}")
            try:
                poll_res = requests.get(poll_url,headers = header,timeout = 10)
            except Exception as e:
                self.logger.warning(f"网络请求异常，{poll_interval}s后重试，batch_id:{batch_id}")
                self.logger.warning(f"异常信息：{str(e)}")
                time.sleep(poll_interval)
                continue
            if poll_res.status_code != 200:
                raise PdfConversionError(f"[任务轮询]失败，状态码：{poll_res.status_code}")
            poll_res_json = poll_res.json()
            if poll_res_json["code"] != 0:
                raise PdfConversionError(f"[任务轮询]失败，错误码{poll_res_json['code']}")
            extract_results = poll_res_json["data"]["extract_result"]
            extract_result = extract_results[0]
            data_state = extract_result["state"]
            if data_state =="done":
                self.log_step(
                    step_name="任务轮询",
                    message=f"解析完成是s,总耗时：{int(elapsed_time)}s,batch_id:{batch_id}"
                )
                full_zip_url = extract_result["full_zip_url"]
                self.log_step(
                    step_name = "任务轮询",
                    message=f"获取全量zip地址成功：{full_zip_url}，总耗时：{int(elapsed_time)}s,batch_id:{batch_id}"
                )
                return full_zip_url
            elif data_state =="failed":
                raise PdfConversionError(f"[任务轮询]失败，错误信息：{extract_result['err_msg']}")
            else:
                self.log_step(
                    step_name="任务轮询",
                    message=f"处理中......已耗时：{int(elapsed_time)}s，状态：{data_state},batch_id:{batch_id}"
                )
                time.sleep(poll_interval)

    def _step_3_download_and_extract(self,zip_url:str,output_dir_obj:Path,pdf_stem:str)->str:
        response = requests.get(zip_url)
        if response.status_code != 200:
            raise FileProcessingError("下载失败")
        zip_save_path = output_dir_obj / f"{pdf_stem}_result.zip"
        with open(zip_save_path,"wb") as f:
            f.write(response.content)
        self.log_step("ZIP下载","下载成功")
        extract_target_dir = output_dir_obj / pdf_stem
        if extract_target_dir.exists():
            shutil.rmtree(extract_target_dir)
        extract_target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_save_path,"r") as zip_file_obj:
            zip_file_obj.extractall(extract_target_dir)
        self.log_step("ZIP下载","解压完成")
        target_md_file = extract_target_dir / "full.md"
        new_md_path = target_md_file.with_name(f"{pdf_stem}.md")
        target_md_file.rename(new_md_path)
        return str(new_md_path.absolute())

if __name__ == "__main__":
    setup_logging()
    init_state = {
        "pdf_path":r"D:\ruanjian\13-企业级智能知识库系统项目\day01\资料\04-设备手册汇总\doc\\hak180使用说明书.pdf",
        "file_dir":r"D:\output"
    }
    node_pdf_to_md = NodePDFToMD()
    #使用 对象（）的方式相当于调用了 对象的__call__()
    result = node_pdf_to_md(init_state)
    json_state = json.dumps(result,ensure_ascii=False,indent=4)
    logging.getLogger().info(json_state)
