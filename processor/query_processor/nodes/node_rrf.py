# processor/query_processor/nodes/node_rrf.py
from typing import List, Dict, Any, Tuple

from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.json_format_utils import serialize_json
from utils.task_utils import add_done_task


class NodeRrf(NodeBase):
    name:str = "node_rrf"
    def process(self,state:QueryGraphState)->QueryGraphState:
        embedding_search_list =[
            doc.get("entity") for doc in (state.get('embedding_chunks') or []) if isinstance(doc,dict)
        ]
        hyde_embedding_search_list =[
            doc.get('entity') for doc in (state.get('hyde_embedding_chunks') or []) if isinstance(doc,dict)
        ]
        rrf_inputs = [
            (embedding_search_list,1.0),
            (hyde_embedding_search_list,1.0)
        ]
        rrf_merge_results = self._rrf_merge(rrf_inputs)
        rrf_chunks=[doc for doc,_ in rrf_merge_results]
        state['rrf_chunks'] = rrf_chunks
        add_done_task(state.get("session_id"), self.name, state.get("is_stream"))
        return state

    def _rrf_merge(self,rrf_inputs,k:int=60,max_results:int=None) -> List[Tuple[Dict[str,Any],float]]:
        chunk_scores = {}
        chunk_data = {}
        for rrf_input,weight in rrf_inputs:
            for rank,doc in enumerate(rrf_input,start=1):
                chunk_id = doc.get('chunk_id')
                chunk_scores[chunk_id] = chunk_scores.get(chunk_id,0.0) + weight/(k+rank)
                # 使用 setdefault 保留首次遇到的文档版本(只记录第一次),存进的数据是一个字典，(key,values)
                chunk_data.setdefault(chunk_id,doc)
        unsorted_results = [(chunk_data[cid], score) for cid, score in chunk_scores.items()]
        sorted_results = sorted(unsorted_results, key=lambda x:x[1], reverse=True)
        return sorted_results[:max_results] if max_results else sorted_results


if __name__ == '__main__':
    mock_state = {
        "embedding_chunks": [
            {"entity": {"chunk_id": "chunk_1", "content": "向量搜索结果#1"}},
            {"entity": {"chunk_id": "chunk_2", "content": "向量搜索结果#2"}},
            {"entity": {"chunk_id": "chunk_3", "content": "向量搜索结果#3"}},
        ],
        "hyde_embedding_chunks": [
            {"entity": {"chunk_id": "chunk_1", "content": "HyDE搜索结果#1"}},
            {"entity": {"chunk_id": "chunk_4", "content": "HyDE搜索结果#2"}},
            {"entity": {"chunk_id": "chunk_2", "content": "HyDE搜索结果#3"}},
        ]
    }
    node_rrf = NodeRrf()
    result = node_rrf(mock_state)
    logger.info(serialize_json(result,indent=4))
