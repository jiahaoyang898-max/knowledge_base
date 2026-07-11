import asyncio
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
task_queues = {}
async def long_task(session_id:str,query:str):
    # 创建一个异步协程消息队列
    queue = asyncio.Queue()
    task_queues[session_id] = queue
    for i in range(5):
        msg = f"【{query}】的第{i+1}段回答：xxx{i+1}"
        await queue.put(msg)
        await asyncio.sleep(1)
    await queue.put(None)

class QueryRequest(BaseModel):
    query: str
    session_id: str
@app.post("/submit_query")
async def submit_query(req:QueryRequest,background_tasks:BackgroundTasks):
    background_tasks.add_task(long_task, req.session_id, req.query)
    return {"message":"任务已启动","session_id":req.session_id}
@app.get("/stream/{session_id}")
async def stream_result(session_id:str):
    async def event_generator():
        while session_id not in task_queues:
            await asyncio.sleep(0.1)
        queue = task_queues[session_id]
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield f"data: {msg}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)