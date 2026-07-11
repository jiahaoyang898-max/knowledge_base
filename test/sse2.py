import asyncio

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app=FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/stream/{session_id}")
async def stream_by_session(session_id: str):
    async def event_generator():
        for i in range(5):
            yield f"data: 会话{session_id}-第{i+1}条消息\n\n"
            await asyncio.sleep(1)
        yield f"data: [END]\n\n"
    async def error_event_generator():
        yield "data: 无效会话id\n\n"
        yield f"data: [END]\n\n"
    if session_id == "123":
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        return StreamingResponse(error_event_generator(),media_type="text/event-stream")
if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)