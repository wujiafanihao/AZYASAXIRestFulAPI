"""
routes 包
包含所有 ChatAPI 路由的模块化实现
"""
from .azyasaxiAI import router as aiyasaxi_router
from .tools import router as tools_router
from .weather import router as weather_router
from .chat_history import ChatMessage

__all__ = [
    'aiyasaxi_router',
    'tools_router',
    'weather_router',
    'ChatMessage'
]
