"""
依赖项模块
包含所有共享的依赖函数
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from models import User, UserProfile, AsyncSessionLocal
from config import SECRET_KEY, ALGORITHM

# OAuth2密码授权方案
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token")

async def get_db() -> AsyncSession:
    """
    获取数据库会话的依赖函数
    用于在路由函数中注入数据库会话
    :yield: 数据库会话
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception as e:
            await db.rollback()
            print(f"数据库错误: {e}")
            raise
        finally:
            await db.close()

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取当前已认证用户的依赖函数
    用于保护需要认证的路由
    :param token: JWT令牌
    :param db: 数据库会话
    :return: 当前用户对象
    :raises: HTTPException 如果认证失败
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 解码JWT令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        # 从数据库获取用户
        result = await db.execute(
            select(User, UserProfile)
            .outerjoin(UserProfile)
            .where(User.username == username)
        )
        user_info = result.first()
        
        if not user_info:
            raise credentials_exception
            
        user, profile = user_info
        
        return user
        
    except JWTError:
        raise credentials_exception
