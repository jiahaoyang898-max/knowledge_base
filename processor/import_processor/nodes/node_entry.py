import json
import logging
from pathlib import Path

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError, FileProcessingError, ValidationError
from processor.import_processor.state import ImportGraphState

class NodeEntry(BaseNode):
    name = "node_entry"
    def process(self,state :ImportGraphState):
        import_file_path = state.get("import_file_path")
        if not import_file_path:
            raise StateFieldError(
                field_name = "import_file_path",
                message = "文件路径不能为空",
                expected_type = str
            )
        import_file_path_obj = Path(import_file_path)
        if not import_file_path_obj.exists():
            raise FileProcessingError(message=f"文件{import_file_path_obj.name}不存在")
        if import_file_path_obj.suffix == ".pdf":
            # is_md_read_enabled
            state["is_pdf_read_enabled"] = True
            state["pdf_path"] = import_file_path
        elif import_file_path_obj.suffix == ".md":
            # is_md_read_enabled
            state["is_md_read_enabled"] = True
            state["md_path"] = import_file_path
        else:
            raise ValidationError(message=f"不支持的文件类型{import_file_path_obj.suffix}")
        state["file_title"] = import_file_path_obj.stem
        return state

if __name__ == "__main__":
    setup_logging()
    init_state = {
        "import_file_path": r"D:\ruanjian\13-企业级智能知识库系统项目\day01\资料\04-设备手册汇总\doc\\hak180使用说明书.pdf"
    }
    node_entry =NodeEntry()
    result = node_entry(init_state)
    json_state = json.dumps(result,ensure_ascii = False,indent = 4)
    logging.getLogger().info(json_state)
