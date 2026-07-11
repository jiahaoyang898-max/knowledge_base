# processor/query_processor/nodes/node_search_embedding.py
from pymilvus import MilvusClient

from config.milvus_config import milvus_config
from processor.query_processor.base import NodeBase, T
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.embedding_utils import generate_embeddings
from utils.json_format_utils import serialize_json
from utils.milvus_utils import create_hybrid_search_requests, get_milvus_client, hybrid_search
from utils.task_utils import add_done_task


class NodeSearchEmbedding(NodeBase):
    name :str="node_search_embedding"
    def process(self,state:QueryGraphState)->QueryGraphState:
        try:
            query = state.get("rewritten_query")
            item_names = state.get("item_names")
            embeddings =generate_embeddings([query])
            dense_vec = embeddings.get("dense")[0]
            sparse_vec = embeddings.get("sparse")[0]
            collection_name = milvus_config.chunks_collection
            expr = None
            if item_names:
                expr = f'item_name in {item_names}'
                logger.info(f"过滤条件：{expr}")
            else:
                logger.info("未指定商品名过滤，将全库搜索")
            reqs = create_hybrid_search_requests(
                dense_vector = dense_vec,
                sparse_vector = sparse_vec,
                expr = expr,
                limit=10
            )
            logger.info("开始执行Milvus混合检索...")
            client = get_milvus_client()
            res = hybrid_search(
                client=client,
                collection_name = collection_name,
                reqs = reqs,
                ranker_weights=(0.8,0.2),
                output_fields=["chunk_id","content","item_name"]
            )
            add_done_task(state.get("session_id"), self.name, state.get("is_stream"))
            return {"embedding_chunks":res[0] if res else []}
        except Exception as e:
            logger.exception(f"向量搜索失败：{e}")
            return  {}

if __name__ == "__main__":

    init_state = {
        "rewritten_query": "关于brother HAK180烫金机，如何调节转印温度？",
        "item_names": ["BrotherHAK180烫金机", "BrotherHAK-180烫金机"]
    }
    node_search_embedding = NodeSearchEmbedding()
    result = node_search_embedding(init_state)
    logger.info(serialize_json(result,indent=4))