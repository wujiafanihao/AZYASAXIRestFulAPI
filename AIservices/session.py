"""
会话管理模块
用于创建和管理用户会话
"""

import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from models import Base

# 会话模型，用于持久化存储会话信息
class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)  # 用户ID，确保一个用户只有一个有效会话
    session_id = Column(String, unique=True, index=True)  # 会话ID
    created_at = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now)
    
    # 关系
    user = relationship("User")

class SessionManager:
    """会话管理类"""
    
    def __init__(self):
        # 用户名到会话ID的映射
        self._sessions: Dict[str, str] = {}
        # 用户ID到会话ID的映射
        self._user_id_sessions: Dict[int, str] = {}
        # 会话ID到用户信息的映射 (user_id, username)
        self._session_users: Dict[str, Tuple[int, str]] = {}
        # 会话ID到上次活动时间的映射
        self._session_times: Dict[str, datetime] = {}
    
    async def get_session_id(self, username: str, user_id: int, db: AsyncSession) -> str:
        """获取用户的会话ID，如果不存在则创建新的
        
        现在支持从数据库加载持久化的会话ID
        """
        # 首先检查内存缓存
        if user_id in self._user_id_sessions:
            session_id = self._user_id_sessions[user_id]
            # 确保用户名与会话关联
            self._sessions[username] = session_id
            # 更新会话的最后活动时间
            self._session_times[session_id] = datetime.now()
            return session_id
        
        # 如果内存中没有，尝试从数据库加载
        result = await db.execute(
            select(UserSession).where(UserSession.user_id == user_id)
        )
        user_session = result.scalars().first()
        
        if user_session:
            # 数据库中存在会话记录，更新最后活动时间
            session_id = user_session.session_id
            user_session.last_active = datetime.now()
            await db.commit()
            
            # 更新内存缓存
            self._sessions[username] = session_id
            self._user_id_sessions[user_id] = session_id
            self._session_users[session_id] = (user_id, username)
            self._session_times[session_id] = datetime.now()
            
            return session_id
        
        # 数据库中不存在，创建新的会话ID
        session_id = str(uuid.uuid4())
        
        # 保存到数据库
        new_session = UserSession(
            user_id=user_id,
            session_id=session_id,
            created_at=datetime.now(),
            last_active=datetime.now()
        )
        db.add(new_session)
        await db.commit()
        
        # 更新内存缓存
        self._sessions[username] = session_id
        self._user_id_sessions[user_id] = session_id
        self._session_users[session_id] = (user_id, username)
        self._session_times[session_id] = datetime.now()
        
        return session_id
    
    def is_valid_session(self, session_id: str) -> bool:
        """检查会话ID是否有效"""
        return session_id in self._session_times
    
    def get_username_by_session(self, session_id: str) -> Optional[str]:
        """通过会话ID获取用户名"""
        if session_id in self._session_users:
            return self._session_users[session_id][1]
            
        for username, sid in self._sessions.items():
            if sid == session_id:
                return username
        return None
    
    def get_user_id_by_session(self, session_id: str) -> Optional[int]:
        """通过会话ID获取用户ID"""
        if session_id in self._session_users:
            return self._session_users[session_id][0]
        return None
    
    def get_session_by_user_id(self, user_id: int) -> Optional[str]:
        """通过用户ID获取会话ID"""
        return self._user_id_sessions.get(user_id)
    
    async def clear_session(self, username: str, user_id: int, db: AsyncSession) -> bool:
        """清除用户的会话"""
        if username in self._sessions:
            session_id = self._sessions[username]
            del self._sessions[username]
            
            # 清除用户ID到会话ID的映射
            if user_id in self._user_id_sessions:
                del self._user_id_sessions[user_id]
                
            if session_id in self._session_users:
                del self._session_users[session_id]
                
            if session_id in self._session_times:
                del self._session_times[session_id]
            
            # 从数据库中删除会话
            result = await db.execute(
                select(UserSession).where(UserSession.user_id == user_id)
            )
            user_session = result.scalars().first()
            if user_session:
                await db.delete(user_session)
                await db.commit()
                
            return True
        return False

# 创建全局会话管理器实例
session_manager = SessionManager() 