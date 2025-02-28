"""
用户模块
处理用户相关的路由
"""
from fastapi import APIRouter, Depends
from models import User
from dependencies import get_current_user

# 创建路由器
router = APIRouter(tags=["用户"])

@router.get("/users/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    获取当前用户信息
    这是一个受保护的路由，需要有效的JWT令牌才能访问
    :param current_user: 当前认证用户
    :return: 用户信息
    """
    return current_user
