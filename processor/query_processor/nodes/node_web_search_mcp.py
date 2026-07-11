# processor/query_processor/nodes/node_web_search_mcp.py
import asyncio
import json

from agents.mcp import MCPServerStreamableHttp

from config.bailian_mcp_config import mcp_config
from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.json_format_utils import serialize_json
from utils.task_utils import add_done_task


class NodeWebSearchMcp(NodeBase):
    name:str = "node_web_search_mcp"
    def process(self,state:QueryGraphState)->QueryGraphState:
        query = state.get("rewritten_query","")
        docs = []
        if query:
            result =asyncio.run(self._mcp_call(query))
            if result:
                pages = json.loads(result.content[0].text).get("pages") or []
                for item in pages:
                    snippet = (item.get("snippet") or "").strip()
                    url = (item.get("url") or "").strip()
                    title = (item.get("title") or "").strip()
                    if not snippet:
                        continue
                    docs.append({"title":title,"url":url,"snippet":snippet})
                logger.info(f"Mcp搜索结果：{docs}")
        if docs:
            add_done_task(state.get("session_id"), self.name, state.get("is_stream"))
            return {"web_search_docs":docs}
        return {}
    async def _mcp_call(self,query):
        #MCP HTTP 客户端实例，用于和远程 MCP 服务端通信。
        search_mcp = MCPServerStreamableHttp(
            name="search_mcp",
            params = {
                "url":mcp_config.mcp_base_url,
                "headers":{"Authorization":f"Bearer {mcp_config.api_key}"},
                "timeout":10
            },
            cache_tools_list=True,
            max_retry_attempts=3
        )
        try:
            await search_mcp.connect()#TCP 连接建立、鉴权校验、MCP 协议握手、拉取服务端工具列表
            #search_mcp里的工具（call_tool）
            result = await search_mcp.call_tool(
                tool_name="bailian_web_search",
                arguments={"query":query,"count":5},#传递给搜索工具的业务参数
            )
            return result
        finally:
            await search_mcp.cleanup()#异步清理方法，负责断开 HTTP 连接、释放会话资源、清理临时缓存，避免连接泄漏。


if __name__ == "__main__":
    init_state = {
        "rewritten_query": "关于brother HAK180烫金机，如何调节转印温度？"
    }
    node_web_search_mcp = NodeWebSearchMcp()
    result = node_web_search_mcp(init_state)
    logger.info(serialize_json(result,indent=4))