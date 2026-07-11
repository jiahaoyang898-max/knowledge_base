import uvicorn
from fastapi import FastAPI
from h11 import Response

from tool.logger import logger

app = FastAPI()
@app.get("/items/{item_id}",summary='获取指定参数')
async def read_item(item_id: int,q:str|None=None):
    return {"item_id": item_id, "q": q}

@app.get("/items",summary="分页")
async def read_item(skip:int=0,limit:int=10):
    return {"skip": skip, "limit": limit}

from pydantic import BaseModel
class Item(BaseModel):
    name: str
    price: float
    is_offer: bool
@app.post("/items/",summary="类型检查")
async def create_item(item:Item):
    return {"name": item.name, "price": item.price, "is_offer": item.is_offer}

from fastapi.responses import JSONResponse,FileResponse,HTMLResponse,RedirectResponse,PlainTextResponse,StreamingResponse
@app.get("/api/user")
async def get_user():
    return JSONResponse(
        content={"name":"张三","age":20},
        status_code=200,
        headers ={"X-Custom-Header": "custom-value"}
    )

@app.get("/download/excel")
async def download_excel():
    excel_path = "D:/hak180使用说明书.pdf"
    return FileResponse(
        path=excel_path,
        filename="hak180使用说明书.pdf",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/hello")
async def hello(name:str="游客"):
    html_content =f"""
    <html>
        <body>
            <h1>你好，{name}！</h1>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/text")
async def get_text():
    return PlainTextResponse(content="这是纯文本响应", status_code=200)

@app.get("/old-path")
async def get_old_path():
    return RedirectResponse(url="/new-path", status_code=307)
@app.get("/new-path")
async def get_new_path():
    return {"message":"这是新接口"}

import asyncio
async def generate_stream():
    words = ["你", "好", "，", "这", "是", "流", "式", "响", "应"]
    for word in words:
        await asyncio.sleep(0.5)
        yield word.encode("utf-8")
@app.get("/stream")
async def get_stream():
    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@app.get("/custom")
async def custom_response():
    # 返回二进制数据，指定自定义 MIME 类型
    return Response(
        content="<h1>纯文本</h1>",
        # media_type="text/text",
        media_type="text/html",
        status_code=200)
if __name__ == "__main__":
    logger.info("File Import Service 服务启动中...")
    uvicorn.run(
        app=app,
        host="127.0.0.1",
        port=8001
    )
