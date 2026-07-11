from dotenv import load_dotenv
from langgraph.constants import END
from langgraph.graph import StateGraph

from processor.query_processor.nodes.node_answer_output import NodeAnswerOutput
from processor.query_processor.nodes.node_item_name_confirm import NodeItemNameConfirm
from processor.query_processor.nodes.node_rerank import NodeRerank
from processor.query_processor.nodes.node_rrf import NodeRrf
from processor.query_processor.nodes.node_search_embedding import NodeSearchEmbedding
from processor.query_processor.nodes.node_search_embedding_hyde import NodeSearchEmbeddingHyde
from processor.query_processor.nodes.node_web_search_mcp import NodeWebSearchMcp
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
# 初始化环境变量（类加载前执行，保证全局生效）
load_dotenv()

class KBQueryWorkflow:
    def __init__(self):
        self.workflow = StateGraph(QueryGraphState)
        self._init_nodes()
        self._register_nodes()
        self._setup_routes()
        self._compiled_app = None

    def _init_nodes(self):
        self.node_item_name_confirm = NodeItemNameConfirm()
        self.node_search_embedding = NodeSearchEmbedding()
        self.node_search_embedding_hyde = NodeSearchEmbeddingHyde()
        self.node_web_search_mcp = NodeWebSearchMcp()
        self.node_rrf = NodeRrf()
        self.node_rerank = NodeRerank()
        self.node_answer_output = NodeAnswerOutput()

    def _register_nodes(self):
        self.workflow.add_node("node_item_name_confirm", self.node_item_name_confirm)
        self.workflow.add_node("node_multi_search",lambda x:x)
        self.workflow.add_node("node_search_embedding",self.node_search_embedding)
        self.workflow.add_node("node_search_embedding_hyde", self.node_search_embedding_hyde)
        self.workflow.add_node("node_web_search_mcp",self.node_web_search_mcp)
        self.workflow.add_node("node_join",lambda x:{})
        self.workflow.add_node("node_rrf",self.node_rrf)
        self.workflow.add_node("node_rerank",self.node_rerank)
        self.workflow.add_node("node_answer_output",self.node_answer_output)

    def _route_after_item_name_confirm(self,state:QueryGraphState)->str:
        if state.get("answer"):
            return "node_answer_output"
        return "node_multi_search"
    def _setup_routes(self):
        self.workflow.set_entry_point("node_item_name_confirm")
        self.workflow.add_conditional_edges(
            "node_item_name_confirm",
            self._route_after_item_name_confirm,
            {
                "node_answer_output":"node_answer_output",
                "node_multi_search":"node_multi_search"
            }
        )
        self.workflow.add_edge("node_multi_search","node_search_embedding")
        self.workflow.add_edge("node_multi_search","node_search_embedding_hyde")
        self.workflow.add_edge("node_multi_search","node_web_search_mcp")
        self.workflow.add_edge("node_search_embedding","node_join")
        self.workflow.add_edge("node_search_embedding_hyde","node_join")
        self.workflow.add_edge("node_web_search_mcp","node_join")
        self.workflow.add_edge("node_join","node_rrf")
        self.workflow.add_edge("node_rrf","node_rerank")
        self.workflow.add_edge("node_rerank", "node_answer_output")
        self.workflow.add_edge("node_answer_output",END)

    def compile(self):
        if not self._compiled_app:
            self._compiled_app = self.workflow.compile()
        return self._compiled_app

    def run(self,initial_state:QueryGraphState,stream:bool=False)->QueryGraphState:
        if not self._compiled_app:
            self.compile()
        if stream:
            return self._compiled_app.stream(initial_state)
        else:
            return self._compiled_app.invoke(initial_state)

if __name__ == "__main__":
    init_state ={"original_query":"如何使用万能表测量电压？"}
    workflow = KBQueryWorkflow()
    for chunk in workflow.run(init_state,stream=True):
        logger.info(chunk)
    logger.info(workflow.compile().get_graph().draw_ascii())










