import uvicorn
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi import FastAPI, Request

app=FastAPI()
BASE_DIR = Path(__file__).parent
print("当前文件目录：",BASE_DIR)
static_dir = BASE_DIR / "static"
#这里.mount作用：挂载静态文件路由，让浏览器可以直接访问服务器上的静态资源（图片、css、js、字体、html 文件等）。
app.mount("/static", StaticFiles(directory=static_dir), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)