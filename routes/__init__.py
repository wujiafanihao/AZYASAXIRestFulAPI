"""
routes 包
包含所有 API 路由的模块化实现
"""
from .auth import router as auth_router
from .registration import router as registration_router
from .verification import router as verification_router
from .users import router as users_router
from .chat import router as chat_router

__all__ = [
    'auth_router',
    'registration_router',
    'verification_router',
    'users_router',
    'chat_router',
]
