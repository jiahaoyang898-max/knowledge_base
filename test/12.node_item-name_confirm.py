# processor/query_processor/nodes/node_item_name_confirm.py

import json
from typing import Dict, Any, List, Tuple

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from config.lm_config import lm_config
from processor.query_processor.base import NodeBase
from processor.query_processor.prompt.item_name_confirm import ITEM_NAME_EXTRACT_TEMPLATE, \
    ITEM_NAME_EXTRACT_SYSTEM_PROMPT
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.mongo_history_utils import get_recent_messages, save_chat_message
from utils.json_format_utils import format_json


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
        #步骤3
        message_id = save_chat_message(session_id,"user", original_query)
        logger.info(f"步骤3：用户消息已初始保存，ID:{message_id}")
        #4
        extract_res = self._step_4_extract_info(original_query, history)
        item_names = extract_res.get("item_names")
        rewritten_query = extract_res.get("rewritten_query", original_query)
        # 更新状态
        state["rewritten_query"] = rewritten_query
        state["item_names"] = item_names

    def _step_1_validate_param(self,state: QueryGraphState) -> Tuple[str,str]:
        session_id = state.get("session_id")
        if not session_id:
            raise ValueError("核心参数session_id缺失")
        original_query = state.get("original_query")
        if not original_query:
            raise ValueError("核心参数original_query缺失")
        return session_id,original_query
    def _step_4_extract_info(self, query, history) -> Dict:
        """
        利用LLM从当前问题以及历史会话中提取出主要询问的商品名称item_names（可多个，JSON列表形式）
        若商品名不够明确则返回空列表，同时根据上下文重新改写问题，保证问题独立完整
        :param query: 字符串 - 用户当前原始查询问题（如："这个多少钱？"）
        :param history: 列表[字典] - 近期会话历史，每条消息含role/text等字段，
                        格式：[{"role": "user/assistant", "text": "消息内容", "_id": "消息ID"}, ...]
        :return: 字典 - 提取结果，固定包含2个字段，格式：
                 {
                     "item_names": ["商品名1", "商品名2", ...],  # 提取的商品名列表，无则空列表
                     "rewritten_query": "改写后的完整问题"       # 包含商品名的独立问题，无则返回原始query
                 }
        """

        try:
            # 1. 获取llm客户端
            chat_model = ChatOpenAI(
                model=lm_config.item_model,
                api_key=lm_config.api_key,
                base_url=lm_config.base_url,
                temperature=lm_config.llm_temperature,
                # 开启JSON标准输出模式，强制模型返回可解析的json_object
                model_kwargs={
                    "response_format": {"type": "json_object"}
                }
            )

            # 2. 构造历史对话文本，拼接为"角色: 内容"的格式，供LLM做上下文理解
            history_text = ""
            for msg in history:
                role = msg.get("role")
                content = msg.get("text")
                history_text += f"{role}: {content}\n"

            # 3. 处理和动态拼接提示词
            # 为了把大括号当作 “普通字符” 保留下来，用双大括号 {{ 表示普通的左大括号 {，双大括号 }} 表示普通的右大括号 }。
            user_prompt = ITEM_NAME_EXTRACT_TEMPLATE.format(
                history_text=history_text,
                query=query
            )

            # 4. 构造LLM调用的消息列表，包含系统角色（定义助手身份）和用户角色（传入提示词）
            messages = [
                SystemMessage(content=ITEM_NAME_EXTRACT_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ]


            # 5. 调用LLM客户端，发起请求获取结果
            response = chat_model.invoke(messages)
            content = response.content

            # 6. 数据清洗：处理LLM可能返回的代码块格式（如```json ... ```），去除包裹符
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "")

            # 7. 数据解析：将JSON字符串转为字典
            result = json.loads(content)

            # 8. 健壮性处理：确保字段存在
            # 确保返回结果包含item_names字段，无则设为空列表
            if "item_names" not in result:
                result["item_names"] = []
            # 确保返回结果包含rewritten_query字段，无则复用原始查询
            if "rewritten_query" not in result:
                result["rewritten_query"] = query

            # 9. 给item_names 去除空格
            result["item_names"] = [
                name.replace(" ", "").replace("\n", "").replace("\t", "").replace("\r", "")
                for name in result["item_names"]
            ]

            # 10、返回解析后的提取结果
            return result

        except Exception as e:
            # 捕获所有异常（如LLM调用失败、JSON解析失败等），记录错误日志
            logger.error(f"大模型调用异常：{e}")
            # 异常时返回默认结果：空商品名列表+原始查询
            return {"item_names": [], "rewritten_query": query}


if __name__ == '__main__':
    init_state = {
        "session_id": "test_session_003",
        "original_query":"怎么调他的转印温度？"
    }
    node_item_name_confirm = NodeItemNameConfirm()
    result = node_item_name_confirm(init_state)
    # 将返回的图状态进行json序列化
    json_state = json.dumps(result,ensure_ascii=False,indent=4)
    logger.info(format_json(result))




