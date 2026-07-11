import re
from typing import List, Dict, Tuple

from langchain_core.prompts import load_prompt

from processor.query_processor.prompt.answer_prompt import ANSWER_PROMPT
from tool.logger import logger

from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from utils.llm_utils import get_llm_client
from utils.mongo_history_utils import save_chat_message
from utils.sse_utils import push_to_session, SSEEvent
from utils.task_utils import add_done_task, set_task_result

MAX_CONTEXT_CHARS = 12000

class NodeAnswerOutput(NodeBase):
    name: str = "node_answer_output"
    def process(self,state: QueryGraphState)->QueryGraphState:
        answer_exists = self._step_1_check_answer(state)
        if not answer_exists:
            prompt = self._step_2_construct_prompt(state)
            state["prompt"] = prompt
            self._step_3_generate_response(state,prompt)
        image_urls = self._extract_images_from_docs(state.get("reranked_docs") or [])
        if state.get("answer"):
            logger.info("---写入MongoDB历史记录---")
            self._step_4_write_history(state,image_urls = image_urls)
        logger.info(f"---发送 final 事件---图片为：{image_urls}")
        if state.get("is_stream"):
            push_to_session(
                state['session_id'],
                SSEEvent.FINAL,
                {
                    "answer": state["answer"],
                    "status":"completed",
                    "image_urls": image_urls
                }
            )
        logger.info("---node_answer_output 节点处理结束---")
        add_done_task(state.get("session_id"), self.name, state.get("is_stream"))
        return state
    def _step_1_check_answer(self,state)->bool:
        answer = state.get("answer")
        is_stream = state.get("is_stream")
        if answer:
            if is_stream:
                logger.info("---step 1:发生已有答案，执行流式推送---")
                push_to_session(state["session_id"],SSEEvent.DELTA,{"delta":answer})
            else:
                set_task_result(state["session_id"],"answer",answer)
            return True
        else:
            return False

    def _step_2_construct_prompt(self,state:QueryGraphState)->str:
        char_budget = MAX_CONTEXT_CHARS
        question=state.get("rewritten_query") or state.get("original_query","")
        item_names = state["item_names"]
        context_str,char_budget = self._format_reranked_docs(state.get("reranked_docs") or [],char_budget)
        history_str,char_budget = self._format_chat_history(state.get("history") or [],char_budget)
        item_names_str = ",".join(item_names) if item_names else "无指定商品"
        prompt=ANSWER_PROMPT.format(
            context = context_str or "无参考内容",
            history = history_str if history_str else "暂无历史对话",
            item_names = item_names_str,
            question = question,
        )
        logger.info(f"组装后的提示词为：{prompt}")
        return prompt
    def _format_reranked_docs(self,reranked_docs:List[Dict],char_budget:int) -> Tuple[str,int]:
        formatted_lines = []
        used_chars = 0
        for idx,doc in enumerate(reranked_docs,start=1):
            content = doc.get("content")
            meta_tags = [f"[{idx}]"]
            for field,template in [
                ("source","[source={}]"),
                ("chunk_id","[chunk_id={}]"),
                ("url","[url={}]"),
                ("title","[title={}]"),
            ]:
                field_value = str(doc.get(field)).strip()
                if field_value:
                    meta_tags.append(template.format(field_value))
            relevance_score = doc.get("score")
            if relevance_score is not None:
                meta_tags.append(f"[score={float(relevance_score):.4f}]")
            doc_entry = " ".join(meta_tags) +"\n" + content
            if used_chars + len(doc_entry) > char_budget:
                break
            formatted_lines.append(doc_entry)
            used_chars += len(doc_entry) + 2
        return "\n\n".join(formatted_lines),char_budget-used_chars
    def _format_chat_history(self,chat_history:List[Dict],char_budget:int) -> Tuple[str,int]:
        formatted_lines = []
        used_chars = 0
        role_label_map = {"user":"用户","assistant":"助手"}
        for message in chat_history:
            role = message.get("role","")
            text = message.get("text","")
            if not text or role not in role_label_map:
                continue
            formatted_line = f"{role_label_map[role]}:{text}"
            used_chars += len(formatted_line) + 1
            if used_chars > char_budget:
                return "\n".join(formatted_lines),char_budget-used_chars
            formatted_lines.append(formatted_line)
        return "\n".join(formatted_lines),char_budget-used_chars

    def _step_3_generate_response(self,state:QueryGraphState,prompt:str)->QueryGraphState:
        logger.info("---Step 3: 开始生成回答 (LLM Generation)---")
        llm = get_llm_client()
        session_id = state.get("session_id")
        is_stream = state.get("is_stream")
        if is_stream:
            logger.info(f"模式: 流式输出 (Streaming), Session: {session_id}")
            final_text = ""
            try:
                for chunk in llm.stream(prompt):
                    delta = getattr(chunk,"content","") or ""
                    if delta:
                        #getattr(object, 属性名, 默认值)
                        #作用：安全读取对象的 content 属性
                        #如果 chunk 对象存在 .content → 返回 chunk.content
                        #如果 chunk 没有 content 属性 → 不报错，返回默认值 ""
                        final_text += delta
                        push_to_session(session_id,SSEEvent.DELTA,{"delta":delta})
                logger.info(f"流式输出完成，总长度: {len(final_text)}")
            except Exception as e:
                logger.error(f"流式生成出错: {e}", exc_info=True)
                push_to_session(session_id, SSEEvent.ERROR, {"error": str(e)})
                state["answer"] = final_text
        else:
            logger.info(f"模式: 非流式输出 (Blocking), Session: {session_id}")
            try:
                response = llm.invoke(prompt)
                content = response.content
                state["answer"] = content
                set_task_result(session_id, "answer", content)
                logger.info(f"生成回答完成，长度: {len(content)}")
            except Exception as e:
                logger.error(f"生成回答出错: {e}", exc_info=True)
                state["answer"] = "抱歉，生成回答时出现错误。"
        return state

    def _extract_images_from_docs(self,docs):
        images = []
        seen = set()
        if not docs:
            return []
        md_img_pattern = re.compile(r'!\[.*?\]\((.*?)\)')
        logger.info(f"开始提取图片，待处理文档数：{len(docs)}")
        for i,doc in enumerate(docs):
            url = (doc.get("url") or "").strip()
            if url:
                if url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg')):
                    if url not in seen:
                        logger.debug(f"文档[{i}]发现图片URL(字段)：{url}")
                        seen.add(url)
                        images.append(url)
            text = (doc.get("content") or "").strip()
            if text:
                matches = md_img_pattern.findall(text)
                for img_url in matches:
                    img_url = img_url.strip()
                    if img_url and img_url not in seen:
                        logger.debug(f"文档[{i}] 正文发现 Markdown 图片: {img_url}")
                        seen.add(img_url)
                        images.append(img_url)
        logger.info(f"图片提取完成，共找到 {len(images)} 张唯一图片: {images}")
        return images

    def _step_4_write_history(self,state:QueryGraphState,image_urls = None)->QueryGraphState:
        session_id = state.get("session_id","default")
        answer = (state.get("answer") or "").strip()
        item_names = state.get('item_names') or []
        try:
            if answer:
                save_chat_message(
                    session_id = session_id,
                    role="assistant",
                    text = answer,
                    rewritten_query="",
                    item_names = item_names,
                    image_urls = image_urls,
                    message_id = None
                )
        except Exception as e:
            logger.error(f"写入Mongo历史记录失败：{e}")
        return state
if __name__ == "__main__":
    logger.info("开始测试: 答案生成节点")
    mock_reranked_docs = [
        {
            "chunk_id": "local_101",
            "source": "local",
            "title": "HAK 180 烫金机操作手册_v2",
            "score": 0.95,
            "url": None,
            "content": """
            HAK 180 烫金机的操作面板位于机器正前方。
            开启电源后，您需要先设置温度，默认建议设置在 110℃ 左右。
            具体的操作面板布局请参考下图：
            ![操作面板布局图](http://local-server/images/panel_view.jpg)
            如果是进行局部烫金，请调节侧面的旋钮。
            ![侧面旋钮细节](http://local-server/images/knob_detail.png)
            """
        },
        {
            "chunk_id": None,
            "source": "web",
            "title": "HAK 180 常见故障排除 - 官网",
            "score": 0.88,
            "url": "http://example.com/hak180_troubleshooting.jpeg", # 这是一个直接指向图片的URL（虽然少见，但用于测试提取）
            "content": "如果机器无法加热，请检查保险丝是否熔断..."
        },
        {
            "chunk_id": "local_102",
            "source": "local",
            "title": "安全注意事项",
            "score": 0.82,
            "url": None,
            "content": "操作时请务必佩戴隔热手套，避免高温烫伤。"
        }
    ]
    mock_history = [
        {"role": "user", "text": "你好，这款机器怎么用？"},
        {"role": "assistant", "text": "您好！请问您具体指的是哪一款机器？"},
        {"role": "user", "text": "HAK 180 烫金机"}
    ]
    mock_state = {
        "session_id": "test_answer_session_001",
        "original_query": "HAK 180 烫金机怎么操作？",
        "rewritten_query": "HAK 180 烫金机的具体操作步骤和面板设置方法",
        "item_names": ["HAK 180 烫金机"],
        "history": mock_history,
        "reranked_docs": mock_reranked_docs,
        "is_stream": False, # 测试非流式
        # "is_stream": True, # 若要测试流式，需确保 SSE 环境或 mock 相关函数
        "answer": None # 初始无答案
    }
    node_answer_output = NodeAnswerOutput()
    result = node_answer_output(mock_state)
    if "prompt" in result:
        print(f"[PASS]Prompt 构建成功(长度：{len(result['prompt'])})")
    else:
        print("[FAIL]Prompt 未构建")
    answer = result.get("answer")
    if answer and len(answer) > 10:
        print(f"[PASS] 答案生成成功 (长度: {len(answer)})")
        print(f"答案预览: {answer[:50]}...")
    else:
        print(f"[WARN] 答案生成可能异常 (Content: {answer})")
    # 3. 验证图片提取
    print("[INFO] 请检查上方日志中是否包含 '图片提取完成' 及以下 URL:")
    print(" - http://local-server/images/panel_view.jpg")
    print(" - http://local-server/images/knob_detail.png")







