"""
启动脚本
用于在正确的事件循环下启动FastAPI应用
"""
import asyncio
import platform
import uvicorn

def main():
    """
    主函数，设置事件循环并启动FastAPI应用
    """
    # 在Windows环境下设置ProactorEventLoop
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print("已设置WindowsProactorEventLoopPolicy")
    
    # 启动FastAPI应用
    uvicorn.run(
        "api:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main() 