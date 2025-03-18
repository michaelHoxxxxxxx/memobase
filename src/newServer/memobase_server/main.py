from fastapi import FastAPI
from .core.config import settings
from .api.v1.endpoints import users
from contextlib import asynccontextmanager
 
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时的操作
    yield
    # 关闭时的操作
 
app = FastAPI(
    title="Memobase API",
    version=settings.API_VERSION,
    lifespan=lifespan
)
 
# 添加路由
app.include_router(users.router, prefix=f"{settings.API_PREFIX}/users", tags=["users"])
 
@app.get("/health")
async def health_check():
    return {"status": "healthy"}