import json
import logging
import re
from pathlib import Path
from typing import Tuple, List, Dict

from langchain_text_splitters import RecursiveCharacterTextSplitter

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError
from processor.import_processor.state import ImportGraphState

class NodeDocumentSplit(BaseNode):
    name = "node_document_split"
    def process(self,state: ImportGraphState)->ImportGraphState:
        content,file_title = self._step_1_get_inputs(state)
        sections,title_count,lines_count = self._step_2_split_by_titles(content,file_title)
        sections = self._step_3_handle_no_title(content,sections,title_count,file_title)
        sections =self._step_4_refine_chunks(sections)
        self._step_5_print_stats(lines_count,sections)
        self._step_6_backup(state,sections)
        state["chunks"] = sections
        return state
    def _step_1_get_inputs(self,state:ImportGraphState)->Tuple[str,str]:
        file_title = state.get("file_title")
        if not file_title:
            raise StateFieldError(field_name="file_title",message="文件标题不能为空",expected_type = str)
        md_path = state.get("md_path")
        if not md_path:
            raise StateFieldError(field_name="md_path",message="MD路径不能为空",expected_type = str)
        md_content = state.get("md_content")
        if not md_content:
            raise StateFieldError(field_name = "md_content",message="文件内容不能为空",expected_type = str)
        md_content = md_content.replace("\r\n","\n").replace("\r","\n")
        return md_content,file_title

    def _step_2_split_by_titles(self,content:str,file_title:str)->Tuple[List[Dict[str,str]],int,int]:
        title_pattern = r'\s*#{1,6}\s+.+'
        lines = content.split("\n")
        sections = []
        title_count = 0
        current_title = ""
        current_lines = []
        in_code_block = False
        def _flush_section():
            if not current_lines:
                return
            sections.append(
                {
                    "title": current_title,
                    "content":"\n".join(current_lines),
                    "file_title": file_title,
                }
            )
        for line in lines:
            striped_line = line.strip()
            if striped_line.startswith("```") or striped_line.startswith("~~~"):
                in_code_block = not in_code_block
                current_lines.append(striped_line)
                continue
            is_valid_title = (not in_code_block) and re.match(title_pattern,line)
            if is_valid_title:
                _flush_section()
                current_title = striped_line
                current_lines = [current_title]
                title_count += 1
                self.logger.info(f"识别标题：{current_title}")
            else:
                current_lines.append(striped_line)
        _flush_section()
        self.logger.info(f"文档粗切(按标题切分)完成，共{len(sections)}个章节，标题数量是{title_count}，文本共有{len(lines)}行")
        return sections,title_count,len(lines)

    def _step_3_handle_no_title(self,content:str,sections:List[Dict[str,str]],title_count:int,file_title:str)->List[Dict[str,str]]:
        if title_count == 0 :
            self.logger.warning(f"步骤3：未识别到任何MD标题，将全文作为单个章节处理，文件：{file_title}")
            return [{
                "title":"无标题",
                "content":content,
                "file_title":file_title,
            }]
        self.logger.debug(f"步骤3：检测到{title_count}个有效标题，无需兜底处理")
        return sections

    def _step_4_refine_chunks(self,sections:List[Dict[str,str]]) -> List[Dict[str,str]]:
        refined_split = []
        for section in sections:
            sub_sections = self._split_long_section(section)
            refined_split.extend(sub_sections)
        self.logger.info(f"步骤4-1：超长章节切分完成，共生成{len(refined_split)}个初始子Chunk")
        final_sections = self._merge_short_sections(refined_split)
        self.logger.info(f"步骤4-2:过短章节合并完成，最终得到{len(final_sections)}个Chunk")
        for sec in final_sections:
            if not sec.get("parent_title"):
                sec["parent_title"] = sec.get("title") or ""
        self.logger.debug(f"步骤4-3：父标题兜底完成，所有Chunk均包含parent_title字段")
        return final_sections
    def _split_long_section(self,section:Dict[str,str]) -> List[Dict[str,str]]:
        content = section.get("content")
        if len(content) <= self.config.max_content_length :
            return [section]
        title = section.get("title")
        prefix = f"{title}\n\n" if title else ""
        available_len =self.config.max_content_length - len(prefix)
        if available_len <= 0:
            self.logger.warning("章节标题过长，无法切分")
            return [section]
        body = content
        if title and body.lstrip().startswith(title):
            body =body[body.find(title)+len(title):].lstrip()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=available_len,
            chunk_overlap=0,
            separators=[
                "\n\n",
                "\n",
                "。",
                "？",
                "！",
                "；",
                ".",
                "?",
                "!",
                ";",
                " ",
            ]
        )
        sub_sections = []
        chunks = splitter.split_text(body)
        for idx, chunk in enumerate(chunks,start=1):
            text = chunk.strip()
            if not text :
                continue
            full_text = (prefix + text).strip()
            new_title = f"{title}{idx}"
            sub_sections.append(
                {
                    "parent_title":title,
                    "title":new_title,
                    "content":full_text,
                    "part":idx,
                    "file_title":section.get("file_title")
                }
            )
        return sub_sections
    def _merge_short_sections(self,sections:List[Dict[str,str]]) -> List[Dict[str,str]]:
        if not sections:
            return []
        merged_sections = []
        current_chunk = None
        for section in sections:
            if current_chunk is None:
                current_chunk = section
                continue
            is_current_short = len(current_chunk["content"]) < self.config.min_content_length
            is_same_parent = current_chunk.get("parent_title") == section.get("parent_title")
            if is_current_short and is_same_parent:
                parent_title = section.get("parent_title")
                section_content = section.get("content")
                if parent_title and section_content.startswith(parent_title):
                    section_content = section_content[len(parent_title):].lstrip()
                current_chunk["content"] += "\n\n" + section_content
                if "part" in section:
                    current_chunk["part"] = section["part"]
            else:
                merged_sections.append(current_chunk)
                current_chunk = section
        if current_chunk is not None:
            merged_sections .append(current_chunk)
        return merged_sections

    def _step_5_print_stats(self,lines_count:int,sections:List[Dict[str,str]]) -> None:
        chunk_num = len(sections)
        self.logger.info("-"*50 + "文档切分统计信息" + "-"*50)
        self.logger.info(f"MD原始文本总行数：{lines_count}")
        self.logger.info(f"最终生成Chunk数量:{chunk_num}")

    def _step_6_backup(self,state:ImportGraphState,sections:List[Dict[str,str]]) -> None:
        try:
            backup_path =Path(state["md_path"]).parent/"chunks.json"
            with open(backup_path,"w",encoding="utf-8") as f:
                json.dump(
                    sections,
                    f,
                    ensure_ascii=False,
                    indent=2
                )
            self.logger.info(f"步骤6：Chunk结果备份成功，备份文件路径：{backup_path}")
        except Exception as e:
            self.logger.error(f"步骤6：Chunk结果备份失败，错误信息：{str(e)}",exc_info = False)

if __name__ == "__main__":
    setup_logging()
    md_path = r"D:\ruanjian\13-企业级智能知识库系统项目\奇妙的自然界.md"
    with open(md_path,"r",encoding="utf-8") as f:
        md_content = f.read()
    init_state = {
        "md_path": md_path,
        "md_content": md_content,
        "file_title": "奇妙的自然界"
    }
    node_document_split = NodeDocumentSplit()
    result = node_document_split(init_state)
    logging.getLogger().info(json.dumps(result,ensure_ascii=False,indent = 4))
