"""
聊天历史记录管理模块
用于存储和检索与会话关联的聊天历史记录
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship
from models import Base, User

# 聊天消息模型
class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)  # 会话ID
    user_id = Column(Integer, ForeignKey("users.id"))  # 用户ID
    message = Column(Text)  # 用户消息
    response = Column(Text)  # AI响应
    tool_used = Column(String, nullable=True)  # 使用的工具名称，如果有
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    # 关系
    user = relationship("User")

# 聊天历史管理类
class ChatHistoryManager:
    def __init__(self):
        # 会话ID到聊天历史的映射（内存缓存）
        self._histories: Dict[str, List[Dict]] = {}
        # 用户ID到会话ID的映射
        self._user_sessions: Dict[int, str] = {}
    
    def add_message(self, session_id: str, user_message: str, ai_response: str, tool_used: Optional[str] = None):
        """添加一条新的聊天记录到内存缓存"""
        if session_id not in self._histories:
            self._histories[session_id] = []
        
        self._histories[session_id].append({
            "user_message": user_message,
            "ai_response": ai_response,
            "tool_used": tool_used,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def get_history(self, session_id: str) -> List[Dict]:
        """从内存缓存获取指定会话的聊天历史记录"""
        return self._histories.get(session_id, [])
    
    def clear_history(self, session_id: str) -> bool:
        """清除内存缓存中的聊天历史记录"""
        if session_id in self._histories:
            del self._histories[session_id]
            return True
        return False
    
    def map_user_to_session(self, user_id: int, session_id: str):
        """将用户ID映射到会话ID"""
        self._user_sessions[user_id] = session_id
    
    def get_session_by_user(self, user_id: int) -> Optional[str]:
        """通过用户ID获取会话ID"""
        return self._user_sessions.get(user_id)
    
    async def save_to_db(self, db: AsyncSession, user_id: int, session_id: str, 
                         user_message: str, ai_response: str, tool_used: Optional[str] = None):
        """将聊天记录保存到数据库"""
        try:
            chat_message = ChatMessage(
                session_id=session_id,
                user_id=user_id,
                message=user_message,
                response=ai_response,
                tool_used=tool_used
            )
            db.add(chat_message)
            await db.commit()
            
            # 更新内存缓存
            self.add_message(session_id, user_message, ai_response, tool_used)
        except Exception as e:
            await db.rollback()
            raise e
    
    async def load_from_db(self, db: AsyncSession, user_id: int, session_id: str, limit: int = 20) -> List[Dict]:
        """从数据库加载聊天记录
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            session_id: 会话ID
            limit: 最大返回条数，默认20条
            
        Returns:
            按时间顺序排列的聊天历史记录列表
        """
        try:
            result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.user_id == user_id, ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())  # 按时间降序排列，先获取最新的
                .limit(limit)  # 限制返回条数
            )
            messages = result.scalars().all()
            
            # 转换为列表并按时间升序排序
            history = []
            for msg in reversed(messages):  # 反转列表，使其按时间升序排列
                history.append({
                    "user_message": msg.message,
                    "ai_response": msg.response,
                    "tool_used": msg.tool_used,
                    "timestamp": msg.created_at.isoformat()
                })
            
            # 更新内存缓存
            self._histories[session_id] = history
            return history
        except Exception as e:
            print(f"加载聊天历史记录时出错: {e}")
            return []
    
    async def clear_db_history(self, db: AsyncSession, user_id: int, session_id: str) -> bool:
        """清除数据库中的聊天记录"""
        try:
            result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.user_id == user_id, ChatMessage.session_id == session_id)
            )
            messages = result.scalars().all()
            
            if not messages:
                return False
            
            for msg in messages:
                await db.delete(msg)
            
            await db.commit()
            
            # 清除内存缓存
            if session_id in self._histories:
                del self._histories[session_id]
            
            return True
        except Exception as e:
            await db.rollback()
            print(f"清除聊天历史记录时出错: {e}")
            return False

# 创建全局聊天历史管理器实例
chat_history_manager = ChatHistoryManager() 