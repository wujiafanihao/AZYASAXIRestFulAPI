"""
数据库模型定义
"""
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
import os

dbBaseURl = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./Azyasaxi.db")
print(dbBaseURl)

# 数据库配置
DATABASE_URL = dbBaseURl
async_engine = create_async_engine(DATABASE_URL, echo=True)

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# 用户模型
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_online = Column(Boolean, default=False)
    last_active = Column(DateTime, nullable=True)
    current_token = Column(String, nullable=True)
    verification_code = Column(String, nullable=True)
    verification_code_expiry = Column(DateTime, nullable=True)
    create_at = Column(DateTime, default=datetime.now(timezone.utc))

    # 用户关系
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    sent_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.sender_id", back_populates="sender")
    received_friend_requests = relationship("FriendRequest", foreign_keys="FriendRequest.receiver_id", back_populates="receiver")
    friends = relationship(
        "User",
        secondary="friendships",
        primaryjoin="User.id==Friendship.user_id",
        secondaryjoin="User.id==Friendship.friend_id",
        back_populates="friends"
    )

# 用户资料
class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True)
    background_url = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    create_at = Column(DateTime, default=datetime.now(timezone.utc))
    update_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    user = relationship("User", back_populates="profile")

# 好友关系
class Friendship(Base):
    __tablename__ = "friendships"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    friend_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

# 好友申请
class FriendRequest(Base):
    __tablename__ = "friend_requests"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String)  # pending, accepted, rejected
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_friend_requests")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_friend_requests")

# 聊天会话
class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"))  # 始终是消息发送者的ID
    user2_id = Column(Integer, ForeignKey("users.id"))  # 始终是消息接收者的ID
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    last_message_at = Column(DateTime, default=datetime.now(timezone.utc))

    # 关系
    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

# 消息
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    sender_id = Column(Integer, ForeignKey("users.id"))  # 发送者ID
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    is_read = Column(Boolean, default=False)  # 消息是否已读
    read_at = Column(DateTime, nullable=True)  # 读取时间

    # 关系
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])

# 删除其他未使用的表（如果存在）
__all__ = [
    'User', 'UserProfile', 'Friendship', 'FriendRequest',
    'Conversation', 'Message'
]
