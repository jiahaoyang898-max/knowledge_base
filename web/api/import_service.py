import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from starlette.responses import FileResponse

from config.minio_config import minio_config
from processor.import_processor.main_graph import KBImportWorkflow
from tool.logger import logger
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from starlette.middleware.cors import CORSMiddleware

from utils.minio_utils import get_minio_client
from utils.task_utils import add_running_task, add_done_task, update_task_status, get_task_status, get_done_task_list, \
    get_running_task_list

## 1. 创建应用
app = FastAPI(
    title="BOSS智库-导入API",
    description="此文档是BOSS智库导入流程的API接口说明"
)
#2. 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
#. 静态页面路由：返回文件导入前端页面
@app.get("/import.html")
async def get_import_page():
    current_dir_parent_path = Path(__file__).absolute().parent.parent
    html_path = current_dir_parent_path/"page"/"import.html"
    if not html_path.exists():
        raise HTTPException(status_code=404,detail=f"没有查询到页面，地址为：{html_path}")
    return FileResponse(html_path)
# 4. 后台任务：LangGraph全流程执行
def run_graph_task(task_id:str,file_dir:str,import_file_path:str):
    try:
        update_task_status(task_id,"processing")
        init_state = {
            "task_id": task_id,
            "file_dir": file_dir,
            "import_file_path": import_file_path,
        }
        workflow = KBImportWorkflow()
        # 3. 流式执行LangGraph全流程（stream模式：实时获取每个节点的执行结果）
        for event in workflow.run(init_state,stream=True):
            for node_name,node_result in event.items():
                add_done_task(task_id,node_name)
        update_task_status(task_id,"completed")
    except Exception as e:
        update_task_status(task_id,"failed")
        logger.info(f"[{task_id}] LangGraph全流程执行失败，异常信息：{str(e)}", exc_info=True)

# 5. 核心接口：文件上传接口(先执行第五步的post请求，然后执行第四步的get请求)
#BackgroundTasks = “先给前端答复，后台慢慢收尾” 的工具，由框架自动注入，不需要前端传任何参数。
#:param background_tasks: FastAPI后台任务对象，用于异步执行LangGraph流程
@app.post("/upload",summary="文件上传接口",description="支持多文件批量上传，自动触发知识库导入全流程")
async def upload_files(background_tasks: BackgroundTasks, files: List[UploadFile]= File(...)):
    data_based_root_dir = os.getenv("DATA_BASED_ROOT_DIR")
    #拼接文件 / 目录路径，自动处理不同系统的路径分隔符
    data_dir = os.path.join(data_based_root_dir,datetime.now().strftime("%Y%m%d"))
    task_ids = []
    for file in files:
        task_id = str(uuid.uuid4())
        task_ids.append(task_id)
        logger.info(f"[{task_id}]开始处理上传文件，文件名：{file.filename},文件类型：{file.content_type}")
        add_running_task(task_id,"upload_file")
        file_dir = os.path.join(data_dir,task_id)
        os.makedirs(file_dir, exist_ok=True)
        import_file_path = os.path.join(file_dir,file.filename)
        with open(import_file_path,"wb") as file_buffer:
            shutil.copyfileobj(file.file, file_buffer)
        logger.info(f"[{task_id}]文件已保存至本地，路径:{import_file_path}")
        minio_object_name = f"pdf_files/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        try:
            minio_client = get_minio_client()
            minio_bucket_name = minio_config.bucket_name
            #fput_object	本地磁盘文件路径	文件已经存在服务器硬盘上
            minio_client.fput_object(
                bucket_name=minio_bucket_name,
                object_name=minio_object_name,
                file_path=import_file_path,
                content_type=file.content_type,
            )
            logger.info(f"[{task_id}]文件已成功上传至MinIO，桶名：{minio_bucket_name}，对象名：{minio_object_name}")
        except Exception as e:
            #exc_info=True:打印日志时，同时输出完整异常堆栈信息
            logger.warning(f"[{task_id}]文件上传MinIO失败，将继续执行本地处理流程，异常信息：{str(e)}",exc_info=True)
        add_done_task(task_id,"upload_file")
        background_tasks.add_task(run_graph_task,task_id,file_dir,import_file_path)
        logger.info(f"[{task_id}] 已将LangGraph全流程加入后台任务，任务已启动")
        logger.info(f"多文件上传处理完毕，共处理{len(files)}个文件，生成TaskID列表：{task_ids}")
    return {
        "code": 200,
        "message": f"文件上传成功，total:{len(files)}",
        "task_ids": task_ids
    }
# 6. 核心接口：任务状态查询接口
@app.get("/status/{task_id}",summary="任务状态查询",description="根据TaskID查询单个文件的处理进度和全局状态")
async def get_task_progress(task_id: str):
    task_status_info:Dict[str,Any] = {
        "code":200,
        "task_id": task_id,
        "status":get_task_status(task_id),
        "done_list":get_done_task_list(task_id),
        "running_list":get_running_task_list(task_id)
    }
    logger.info(f"[{task_id}] 任务状态查询，当前状态：{task_status_info['status']}，已完成节点：{task_status_info['done_list']}")
    return task_status_info

if __name__ == "__main__":
    uvicorn.run(app=app, host="127.0.0.1", port=8000)





























