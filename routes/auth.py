"""
认证模块
处理用户登录和访问令牌相关的路由
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from models import User
from dependencies import get_db

# 创建路由器
router = APIRouter(tags=["认证"])

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Token(BaseModel):
    """登录请求模型"""
    email: str
    password: str

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    :param plain_password: 明文密码
    :param hashed_password: 数据库中存储的哈希密码
    :return: 密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)

async def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    创建访问令牌
    :param data: 要编码到令牌中的数据
    :param expires_delta: 过期时间增量
    :return: 编码后的JWT令牌
    """
    to_encode = data.copy()
    # 设置令牌过期时间
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    # 使用JWT算法加密数据
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/token", response_model=dict)
async def login_for_access_token(request: Token, db: AsyncSession = Depends(get_db)):
    """
    用户登录接口
    :param request: 包含email和password的登录请求
    :param db: 数据库会话
    :return: 包含访问令牌的响应
    """
    # 查询用户
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalars().first()
    
    # 验证用户是否存在
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 验证密码
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = await create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    
    # 返回令牌
    return {
        "message": "true",
        "access_token": access_token,
        "token_type": "bearer"
    }
