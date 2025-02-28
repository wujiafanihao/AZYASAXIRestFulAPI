"""
注册模块
处理用户注册相关的路由和逻辑
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from passlib.context import CryptContext

from models import User
from dependencies import get_db
from .verification import verify_code, clear_verification_code

# 创建路由器
router = APIRouter(tags=["注册"])

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class RegisterRequest(BaseModel):
    """注册请求模型"""
    username: str
    email: str
    password: str
    verification_code: str

@router.post("/register")
async def register_user(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    用户注册接口
    :param request: 包含username、email、password和verification_code的注册请求
    :param db: 数据库会话
    :return: 注册结果
    """
    # 检查用户名是否已存在
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalars().first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )
    
    # 检查邮箱是否已存在
    result = await db.execute(
        select(User).where(User.email.ilike(request.email))
    )
    email_check = result.scalars().first()
    if email_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已注册",
        )
    
    # 验证邮箱验证码
    if not verify_code(request.email, request.verification_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码无效或已过期",
        )
    
    try:
        # 对密码进行哈希处理
        hashed_password = pwd_context.hash(request.password)
        
        # 创建新用户记录
        new_user = User(
            username=request.username,
            email=request.email,
            hashed_password=hashed_password
        )
        
        # 保存到数据库
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        # 清理验证码
        clear_verification_code(request.email)
        
        return {
            "message": "注册成功",
            "flag": True
        }
        
    except Exception as e:
        # 回滚数据库事务
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册过程中发生错误: {str(e)}"
        )
