# processor/query_processor/nodes/node_item_name_confirm.py

import json
from typing import Dict, Any, List, Tuple

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from config.lm_config import lm_config
from config.milvus_config import milvus_config
from processor.query_processor.base import NodeBase
from processor.query_processor.prompt.item_name_confirm import ITEM_NAME_EXTRACT_TEMPLATE, \
    ITEM_NAME_EXTRACT_SYSTEM_PROMPT
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.embedding_utils import generate_embeddings
from utils.milvus_utils import get_milvus_client, create_hybrid_search_requests, hybrid_search
from utils.mongo_history_utils import get_recent_messages, save_chat_message, update_message_item_names
from utils.json_format_utils import format_json
from utils.task_utils import add_done_task


class NodeItemNameConfirm(NodeBase):
    name: str = "node_item_name_confirm"
    def process(self,state: QueryGraphState) -> QueryGraphState:
        #步骤1
        session_id,original_query= self._step_1_validate_param(state)
        logger.info(f"步骤1：参数校验通过")
        #步骤2
        history = get_recent_messages(session_id)
        logger.info(f"步骤2：获取到{len(history)}条历史消息")
        state["history"] = history
        #步骤3存入数据
        message_id = save_chat_message(session_id,"user", original_query)
        logger.info(f"步骤3：用户消息已初始保存，ID:{message_id}")
        #步骤4提取信息
        extract_res = self._step_4_extract_info(original_query,history)
        item_names = extract_res.get("item_names")
        rewritten_query = extract_res.get("rewritten_query",original_query)
        state["rewritten_query"] = rewritten_query
        state["item_names"] = item_names
        # 步骤5.6如果有提取到商品名，进行搜索和对齐
        align_result = {}
        if len(item_names)>0:
            query_results = self._step_5_vectorize_and_query(item_names)
            logger.info(query_results)
            align_result = self._step_6_align_item_names(query_results)
        else:
            logger.info("Node:未提取到商品名，跳过向量检索")
        state = self._step_7_check_confirmation(state,align_result,history)
        self._step_8_write_history(state,session_id,rewritten_query,message_id)
        add_done_task(state.get("session_id"), self.name, state.get("is_stream"))
        return state


    def _step_1_validate_param(self,state: QueryGraphState) -> Tuple[str,str]:
        session_id = state.get("session_id")
        if not session_id:
            raise ValueError("核心参数session_id缺失")
        original_query = state.get("original_query")
        if not original_query:
            raise ValueError("核心参数original_query缺失")
        return session_id,original_query

    def _step_4_extract_info(self,query,history)->Dict:
        try:
            chat_model = ChatOpenAI(
                model = lm_config.item_model,
                api_key=lm_config.api_key,
                base_url=lm_config.base_url,
                temperature=lm_config.llm_temperature,
                # 开启JSON标准输出模式，强制模型返回可解析的json_object
                model_kwargs={
                    "response_format":{"type":"json_object"}
                }
            )
            history_text = ""
            for msg in history:
                role = msg.get("role")
                content = msg.get("text")
                history_text += f"{role}:{content}\n"
            user_prompt = ITEM_NAME_EXTRACT_TEMPLATE.format(
                history_text = history_text,
                query=query
            )
            messages = [
                SystemMessage(content = ITEM_NAME_EXTRACT_SYSTEM_PROMPT),
                HumanMessage(content = user_prompt)
            ]
            response = chat_model.invoke(messages)
            content = response.content
            if content.startswith("```json"):
                content = content.replace("```json","").replace("```","")
            result = json.loads(content)
            if "item_names" not in result:
                result["item_names"] = []
            if "rewritten_query" not in result:
                result["rewritten_query"] = query
            result["item_names"] = [
                name.replace(" ","").replace("\n","") .replace("\t","").replace("\r","")
                for name in result["item_names"]
            ]
            return result
        except Exception as e:
            logger.error(f"大模型调用异常:{e}")
            return {"item_names": [], "rewritten_query": query}

    def _step_5_vectorize_and_query(self,item_names)->List[Dict]:
        results = []
        client = get_milvus_client()
        if not client:
            logger.error("连接Milvus失败")
            return results
        collection_name = milvus_config.item_name_collection
        embeddings = generate_embeddings(item_names)
        for i in range(len(item_names)):
            try:
                dense_vector = embeddings.get("dense")[i]
                sparse_vector = embeddings.get("sparse")[i]
                reqs = create_hybrid_search_requests(
                    dense_vector=dense_vector,
                    sparse_vector=sparse_vector,
                    limit=5
                )
                search_res = hybrid_search(
                    client=client,
                    collection_name=collection_name,
                    reqs=reqs,
                    ranker_weights=(0.8,0.2),
                    limit=5,
                    norm_score=True,
                    output_fields=["item_name"]
                )
                matches = []
                if search_res and len(search_res)>0:
                    for hit in search_res[0]:
                        matches.append({
                            "item_name": hit.get("entity",{}).get("item_name"),
                            "score":hit.get("distance"),
                        })
                results.append({
                    "extracted_names": item_names[i],
                    "matches": matches,
                })
            except Exception as e:
                logger.error(f"查询商品名 '{item_names[i]}' 时出错: {e}")
        return results

    def _step_6_align_item_names(self,query_results)->dict:
        #测试代码
        # query_results = [
        #     {
        #         'extracted_names': 'T300覆膜机',
        #         'matches': [
        #             {'item_name': 'T300覆膜机', 'score': 0.91},
        #             {'item_name': 'T300全自动覆膜机', 'score': 0.87}
        #         ]
        #     }
        # ]
        # query_results = [
        #     {
        #         'extracted_names': 'L80过油机',
        #         'matches': [
        #             {'item_name': 'L82过油烘干机', 'score': 0.42}
        #         ]
        #     }
        # ]

        # # 样例4：无匹配
        # query_results = [
        #     {
        #         'extracted_names': 'K500切割机',
        #         'matches': []
        #     }
        # ]

        confirmed_item_names:List[str] = []
        options:List[str] = []
        logger.info(f"步骤6：获得待处理的数据源：{query_results}")
        for res in query_results:
            extracted_name = (res.get("extracted_name","")or"").strip()
            matches = res.get("matches",[]) or []
            if not matches:
                continue
            high =[m for m in matches if m.get("score",0) > 0.85]
            mid = [m for m in matches if m.get("score",0) >= 0.6]
            if len(high) == 1:
                confirmed_item_names.append(high[0].get("item_name"))
            if len(high) > 1 :
                picked = None
                if extracted_name:
                    for m in high :
                        if m.get("item_name") == extracted_name:
                            picked = m
                            break
                if not picked:
                    picked = high[0]
                confirmed_item_names.append(picked.get("item_name"))
                continue
            if len(mid) >0:
                for m in mid[:5]:
                    options.append(m.get("item_name"))
        return {
            "confirmed_item_names": list(set(confirmed_item_names)),
            "options": list(set(options)),
        }

    def _step_7_check_confirmation(self,state,align_result,history):
        confirmed = align_result.get("confirmed_item_names",[])
        options = align_result.get("options",[])
        if confirmed:
            ids_to_update = []
            for msg in history:
                if not msg.get("item_names"):
                    mid = msg.get("_id")
                    if mid :
                        ids_to_update.append(str(mid))
            if ids_to_update:
                update_message_item_names(ids_to_update,confirmed)
            state["item_names"]=confirmed
            state["answer"] = ""
            return state
        if options:
            options_str = "、".join(options[:3])
            answer = f"您是想问以下哪个产品：{options_str}？请确定一下型号。"
            state["answer"] = answer
            state["item_names"] = []
            return state
        state["answer"] = "抱歉，未找到相关产品，请提供准确型号以便我为您查询"
        state["item_names"] = []
        return state

    def _step_8_write_history(self,state,session_id,rewritten_query,message_id):
        if state.get("answer"):
            save_chat_message(
                session_id=session_id,
                role="assistant",
                text=state["answer"],
                rewritten_query="",
                item_names=state.get("item_names",[])
            )
        save_chat_message(
            session_id=session_id,
            role="user",
            text=state["original_query"],
            rewritten_query=rewritten_query,
            item_names=state.get("item_names",[]),
            message_id=message_id
        )
        return state



if __name__ == '__main__':
    from bson import json_util
    init_state = {
        "session_id": "test_session_003",
        "original_query":"HAK 180 烫金机怎么用？"
    }
    node_item_name_confirm = NodeItemNameConfirm()
    result = node_item_name_confirm(init_state)
    # 将返回的图状态进行json序列化
    json_state = json_util.dumps(result,ensure_ascii=False,indent=4)
    logger.info(format_json(result))





