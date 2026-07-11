# processor/query_processor/nodes/node_rerank.py

from typing import Dict, Any, List

from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.json_format_utils import serialize_json
from utils.reranker_http_utils import rerank_documents
from utils.task_utils import add_done_task

RERANK_MAX_TOPK : int = 10
RERANK_MIN_TOPK : int = 3
RERANK_GAP_ABS:float = 0.5
RERANK_GAP_RATIO:float = 0.25

class NodeRerank(NodeBase):
    name : str = "node_rerank"
    def process(self,state:QueryGraphState)->QueryGraphState:
        merged_multi_docs : List[Dict[str, Any]] = self._step_1_merge_multi_source_docs(state)
        reranked_docs: List[Dict[str, Any]] = self._step_2_rerank_merged_docs(state,merged_multi_docs)
        cutoff_docs = self._step_3_cliff_cutoff(reranked_docs)
        state['reranked_docs'] = cutoff_docs
        add_done_task(state.get("session_id"), self.name, state.get("is_stream"))
        return state

    def _step_1_merge_multi_source_docs(self,state:QueryGraphState) -> List[Dict[str, Any]]:
        final_docs = []
        for rrf_doc in (state.get('rrf_chunks') or []):
            format_rrf_doc ={
                "content":rrf_doc.get("content"),
                "title":rrf_doc.get("title"),
                "chunk_id":rrf_doc.get("chunk_id"),
                "url":None,
                "source":"local"
            }
            final_docs.append(format_rrf_doc)
        for web_doc in (state.get('web_search_docs') or []):
            format_web_doc = {
                "content": web_doc.get('snippet'),
                "title": web_doc.get('title'),
                "chunk_id": None,
                "url": web_doc.get('url'),
                "source": "web"
            }
            final_docs.append(format_web_doc)
        return final_docs

    def _step_2_rerank_merged_docs(self,state:QueryGraphState,merged_multi_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            user_query = state.get('rewritten_query')
            contents = [doc.get("content") for doc in merged_multi_docs]
            rerank_scores = rerank_documents(user_query, contents)
            scored_docs =[{**doc,"score":score} for doc,score in zip(merged_multi_docs,rerank_scores)]
            sorted_score_docs = sorted(
                scored_docs,
                key=lambda x: x["score"],
                reverse=True
            )
            return sorted_score_docs
        except Exception as e:
            logger.error(f"Rerank 重排序失败:{str(e)}")
            return [{**doc,"score":None} for doc in merged_multi_docs]

    def _step_3_cliff_cutoff(self,ranked_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not ranked_docs:
            return []
        upper_bound = min(RERANK_MAX_TOPK, len(ranked_docs))
        lower_bound = min(RERANK_MIN_TOPK, upper_bound)
        cutoff_pos = upper_bound
        for idx in range(lower_bound-1,upper_bound-1):
            current_score = ranked_docs[idx].get("score")
            next_score = ranked_docs[idx+1].get("score")
            if current_score is None or next_score is None:
                continue
            abs_gap = current_score - next_score
            rel_gap = abs_gap / (abs(current_score)+1e-6)
            if abs_gap >= RERANK_GAP_ABS or rel_gap >= RERANK_GAP_RATIO:
                cutoff_pos = idx+1
                logger.debug(f"断崖检测: 位置 {idx + 1}, abs_gap={abs_gap:.4f}, rel_gap={rel_gap:.4f}")
                break
        return ranked_docs[:cutoff_pos]

if __name__ == "__main__":

    mock_state = {
        "rewritten_query": "怎么测这块主板的短路问题？",
        "rrf_chunks": [
            {
                "chunk_id": "local_1",
                "title": "主板维修手册",
                "content": "主板短路通常表现为通电后风扇转一下就停，可以使用万用表的蜂鸣档测量。"
            },
            {
                "chunk_id": "local_2",
                "title": "闲聊",
                "content": "今天中午去吃猪脚饭吧，这块主板外观很漂亮。"
            },
        ],
        "web_search_docs": [
            {
                "url": "https://example.com/repair",
                "title": "短路查修指南",
                "snippet": "主板通电前先打各主供电电感对地阻值，阻值偏低就是短路。"
            },
            {
                "url": "https://example.com/news",
                "title": "科技新闻",
                "snippet": "苹果发布新款手机，A系列芯片性能提升20%。"
            },
        ],
    }
    node_rerank = NodeRerank()
    result = node_rerank(mock_state)
    logger.info(serialize_json(result,indent=4))
