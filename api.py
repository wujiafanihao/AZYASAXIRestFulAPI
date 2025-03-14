"""
主应用模块
用于初始化FastAPI应用和注册路由
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import platform
from models import Base, async_engine
from routes import (
    auth_router, 
    registration_router, 
    verification_router, 
    users_router,
    chat_router,
)
from AIservices import (
    aiyasaxi_router,
    tools_router,
    weather_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用程序生命周期管理器
    :param app: FastAPI应用实例
    """
    print("正在启动服务...")
    # 在Windows环境下设置ProactorEventLoop
    if platform.system() == 'Windows':
        loop = asyncio.get_event_loop()
        if not isinstance(loop, asyncio.ProactorEventLoop):
            asyncio.set_event_loop(asyncio.ProactorEventLoop())
            print("已设置ProactorEventLoop用于Windows环境")
    
    # 启动时初始化数据库表
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    print("正在关闭服务...")

# 创建FastAPI应用实例
app = FastAPI(
    title="用户认证系统",
    description="提供用户注册、登录和验证码等功能的REST API",
    version="1.0.0",
    lifespan=lifespan
)

# 注册路由
app.include_router(auth_router, prefix="/api/v1")
app.include_router(registration_router, prefix="/api/v1")
app.include_router(verification_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(aiyasaxi_router, prefix="/api/v1")
app.include_router(tools_router, prefix="/api/v1")
app.include_router(weather_router, prefix="/api/v1")

# 根路由
@app.get("/")
async def root():
    """
    根路由
    :return: 欢迎信息
    """
    return {
        "message": "欢迎使用用户认证系统",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }
