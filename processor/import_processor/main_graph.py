import logging
from typing import final

from langgraph.constants import END
from langgraph.graph import StateGraph

from processor.import_processor.base import setup_logging
from processor.import_processor.nodes.node_bge_embedding import NodeBGEEmbedding
from processor.import_processor.nodes.node_document_split import NodeDocumentSplit
from processor.import_processor.nodes.node_entry import NodeEntry
from processor.import_processor.nodes.node_import_milvus import NodeImportMilvus
from processor.import_processor.nodes.node_item_name_recognition import NodeItemNameRecognition
from processor.import_processor.nodes.node_md_img import NodeMDImg
from processor.import_processor.nodes.node_pdf_to_md import NodePDFToMD
from processor.import_processor.state import ImportGraphState

class KBImportWorkflow:
    def __init__(self):
        """
        初始化工作流对象
        """
        self._compiled_graph = None
    @property
    def graph(self):
        """
        延迟加载（懒加载）：只在第一次使用工作流对象的时候编译图
        :return:
        """
        if self._compiled_graph is None:
            self._compiled_graph = self.build_graph()
        return self._compiled_graph
    def build_graph(self):
        graph = StateGraph(ImportGraphState)
        graph.add_node("node_entry",NodeEntry())
        graph.add_node("node_pdf_to_md",NodePDFToMD())
        graph.add_node("node_md_img",NodeMDImg())
        graph.add_node("node_document_split",NodeDocumentSplit())
        graph.add_node("node_item_name_recognition",NodeItemNameRecognition())
        graph.add_node("node_bge_embedding",NodeBGEEmbedding())
        graph.add_node("node_import_milvus",NodeImportMilvus())
        graph.set_entry_point("node_entry")
        graph.add_conditional_edges(
            "node_entry",
            self.route_after_entry,
            {
                "node_pdf_to_md":"node_pdf_to_md",
                "node_md_img":"node_md_img",
                END:END
            }
        )
        graph.add_edge("node_pdf_to_md", "node_md_img")
        graph.add_edge("node_md_img", "node_document_split")
        graph.add_edge("node_document_split", "node_item_name_recognition")
        graph.add_edge("node_item_name_recognition", "node_bge_embedding")
        graph.add_edge("node_bge_embedding", "node_import_milvus")
        graph.add_edge("node_import_milvus", END)
        return graph.compile()
    @staticmethod
    def route_after_entry(state:ImportGraphState)->str:
        if state.get("is_pdf_read_enabled"):
            return "node_pdf_to_md"
        elif state.get("is_md_read_enabled"):
            return "node_md_img"
        else:
            return END
    def run(self,state:ImportGraphState,stream:bool=False):
        if stream:
            return self.graph.stream(state)
        else:
            return self.graph.invoke(state)
if __name__ == "__main__":
    setup_logging()
    init_state = {"import_file_path":r"D:\hak180使用说明书.pdf",
                  "file_dir": r"D:\output"}
    workflow = KBImportWorkflow()
    res = workflow.run(init_state)
    logging.getLogger().info(res)
    logging.getLogger().info(workflow.graph.get_graph().draw_ascii())









