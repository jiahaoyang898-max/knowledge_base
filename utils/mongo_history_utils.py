# utils/mongo_history_utils.py

# 导入系统模块：用于读取环境变量
import os
# 导入日志模块：用于记录程序运行日志（成功/失败/错误信息）
import logging
# 导入类型注解模块：用于函数参数/返回值的类型提示，提升代码可读性和规范性
from typing import List, Dict, Any, Optional
# 导入时间模块：用于生成时间戳，记录对话的创建时间
from datetime import datetime


# 导入pymongo核心模块：MongoDB原生Python驱动，实现数据库连接和操作
# ASCENDING：表示升序排序，用于MongoDB索引和查询排序
from pymongo import MongoClient, ASCENDING
# 导入bson的ObjectId：MongoDB默认的主键类型，用于唯一标识文档
from bson import ObjectId
# 导入dotenv模块：用于从.env文件加载环境变量，避免硬编码敏感配置（如MongoDB连接地址）
from dotenv import load_dotenv

# 加载.env文件中的环境变量，使os.getenv能读取到配置
load_dotenv()

class HistoryMongoTool:
    def __init__(self):
        try:
            self.mongo_url = os.getenv("MONGO_URL")
            self.db_name = os.getenv("MONGO_DB_NAME")
            self.client = MongoClient(self.mongo_url)
            self.db = self.client[self.db_name]
            self.chat_message = self.db["chat_message"]
            self.chat_message.create_index([("session_id,1"),("ts",-1)])
            logging.info(f"Successfully connected to MongoDB:{self.db_name}")
        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {e}")
            raise
_history_mongo_tool = HistoryMongoTool()
def get_history_mongo_tool() -> HistoryMongoTool:
    global _history_mongo_tool
    if _history_mongo_tool is None:
        _history_mongo_tool = HistoryMongoTool()
    return _history_mongo_tool
#清理历史数据
def clear_history(session_id:str)-> int:
    mongo_tool = get_history_mongo_tool()
    try:
        result = mongo_tool.chat_message.delete_many({"session_id": session_id})
        logging.info(f"Deleted {result.deleted_count} messages for session {session_id}")
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error clearing history for session {session_id}: {e}")
        return 0
#写入/更新单条会话记录到MongoDB
def save_chat_message(
        session_id:str,
        role:str,
        text:str,
        rewritten_query:str ="",
        item_names:List[str] = None,
        image_urls:List[str] = None,
        message_id:str = None
)->str:
    ts = datetime.now().timestamp()
    document = {
        "session_id": session_id,
        "role": role,
        "text": text,
        "rewritten_query": rewritten_query or "",
        "item_names": item_names,
        "image_urls": image_urls,
        "ts":ts
    }
    mongo_tool = get_history_mongo_tool()
    if message_id:
        result = mongo_tool.chat_message.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": document}
        )
        return message_id
    else:
        result = mongo_tool.chat_message.insert_one(document)
        return str(result.inserted_id)
#批量更新历史会话记录的关联商品名称
def update_message_item_names(
        ids:List[str],
        item_names:List[str]
)->int:
    mongo_tool = get_history_mongo_tool()
    try:
        object_ids = [ObjectId(i) for i in ids]
        result = mongo_tool.chat_message.update_many(
            {
                "_id": {"$in": object_ids},
            },
            {"$set": {"item_names": item_names}}
        )
        logging.info(f"Updated {result.modified_count} records to item_names: {item_names}")
        return result.modified_count
    except Exception as e:
        logging.error(f"Error updating history item_names: {e}")
        return 0
#查询指定会话的最近N条对话记录，返回原始字典格式
def get_recent_messages(session_id:str,limit:int=10)->List[Dict[str, Any]]:
    mongo_tool = get_history_mongo_tool()
    try:
        query = {"session_id": session_id}
        cursor = mongo_tool.chat_message.find(query).sort("ts", ASCENDING).limit(limit)
        messages = list(cursor)
        return messages
    except Exception as e:
        logging.error(f"Error getting recent messages: {e}")
        return []

# 主程序入口：仅当直接运行该脚本时执行，用于简单的功能测试
# if __name__ == "__main__":
#     # 简单测试代码：验证数据库的写入和查询功能是否正常
#     # 测试会话ID，用于标识测试的对话记录
#     sid = "000015_hybrid"
#     # 1. 写入用户消息
#     save_chat_message(sid, "user", "你好 (Hybrid)")
#     # 2. 写入助手回复
#     save_chat_message(sid, "assistant", "你好！我是基于原生 Mongo + LangChain 对象的助手。")
#     # 3. 写入带关联商品的用户消息
#     save_chat_message(sid, "user", "这个万用表怎么换电池？", item_names=["混合万用表"])
#
#     # 4. 查询指定会话的最近5条记录，验证查询功能
#     print("--- 查询 LangChain 对象记录 ---")
#     messages = get_recent_messages(sid, limit=5)
#     # 打印查询到的记录数量
#     print(f"查询到的记录数: {len(messages)}")
#     # 遍历打印每条记录的详细内容
#     for m in messages:
#         print(f" {m}  ")

# if __name__ == "__main__":
    # 测试会话，用于确认商品名称是否能正确的提取
    # sid = "test_session_002"
    # # 1. 写入用户消息
    # save_chat_message(sid, "user", "你好，有烫金机吗？")
    # # 2. 写入助手回复
    # save_chat_message(sid, "assistant", "你好！请问你想询问哪个型号？")
    # # 3. 写入带关联商品的用户消息
    # save_chat_message(sid, "user", "brother的HAK180烫金机")
    # save_chat_message(sid, "assistant", "有的")

if __name__ == "__main__":
    # 测试会话，用于确认商品名称是否能正确的提取
    sid = "test_session_003"
    # 1. 写入用户消息
    save_chat_message(sid, "user", "你好，有万用表吗？")
    # 2. 写入助手回复
    save_chat_message(sid, "assistant", "你好！请问你想询问哪个型号？")
    # 3. 写入带关联商品的用户消息
    save_chat_message(sid, "user", "RS12万用表")
    save_chat_message(sid, "assistant", "有的")

# 主程序入口：仅当直接运行该脚本时执行，用于简单的功能测试
# if __name__ == "__main__":
#     # 测试会话，用于确认商品名称是否能正确的提取
#     sid = "test_session_004"
#     # 1. 写入用户消息
#     save_chat_message(sid, "user", "你好，请问有烫金机吗")
#     # 2. 写入助手回复
#     save_chat_message(sid, "assistant", "你好！请问你想询问哪个型号？")
#     # 3. 写入带关联商品的用户消息
#     save_chat_message(sid, "user", "HAK180和HAK181都可以")
#     save_chat_message(sid, "assistant", "有的")