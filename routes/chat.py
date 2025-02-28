"""
聊天模块，处理私聊相关功能
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, desc, func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta

from models import User, Conversation, Message, Friendship
from dependencies import get_current_user, get_db

router = APIRouter(tags=["聊天"])

# 请求模型
class MessageCreate(BaseModel):
    """发送消息请求模型"""
    to_username: str  # 接收者用户名
    content: str

class MessageSearch(BaseModel):
    """消息搜索请求模型"""
    conversation_id: int
    content: str  # 搜索关键词

# API路由
@router.get("/conversations")
async def get_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的所有会话列表"""
    # 查询所有相关会话
    result = await db.execute(
        select(Conversation)
        .where(
            or_(
                Conversation.user1_id == current_user.id,
                Conversation.user2_id == current_user.id
            )
        )
        .order_by(desc(Conversation.last_message_at))
    )
    conversations = result.scalars().all()

    # 处理会话列表
    conv_list = []
    for conv in conversations:
        # 获取对话的另一方用户信息
        other_user_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id
        user_result = await db.execute(
            select(User).where(User.id == other_user_id)
        )
        other_user = user_result.scalar()

        # 获取最后一条消息
        last_msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        last_msg = last_msg_result.scalar()

        # 获取未读消息数
        unread_result = await db.execute(
            select(func.count(Message.id))
            .where(
                and_(
                    Message.conversation_id == conv.id,
                    Message.sender_id != current_user.id,
                    Message.is_read == False
                )
            )
        )
        unread_count = unread_result.scalar()

        conv_list.append({
            "conversation_id": conv.id,
            "other_user": {
                "id": other_user.id,
                "username": other_user.username,
                "email": other_user.email
            },
            "last_message": {
                "content": last_msg.content if last_msg else None,
                "sender_id": last_msg.sender_id if last_msg else None,
                "created_at": last_msg.created_at.isoformat() if last_msg else None,
                "is_read": last_msg.is_read if last_msg else None
            } if last_msg else None,
            "unread_count": unread_count,
            "created_at": conv.created_at.isoformat(),
            "last_message_at": conv.last_message_at.isoformat()
        })

    return conv_list

@router.post("/messages")
async def send_message(
    message: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """发送消息"""
    # 查找接收者
    result = await db.execute(
        select(User).where(User.username == message.to_username)
    )
    receiver = result.scalar()
    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    if receiver.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能给自己发送消息"
        )

    # 验证是否为好友
    result = await db.execute(
        select(Friendship).where(
            or_(
                and_(
                    Friendship.user_id == current_user.id,
                    Friendship.friend_id == receiver.id
                ),
                and_(
                    Friendship.user_id == receiver.id,
                    Friendship.friend_id == current_user.id
                )
            )
        )
    )
    if not result.scalar():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能给好友发送消息"
        )

    # 查找或创建会话
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Conversation).where(
            or_(
                and_(
                    Conversation.user1_id == current_user.id,
                    Conversation.user2_id == receiver.id
                ),
                and_(
                    Conversation.user1_id == receiver.id,
                    Conversation.user2_id == current_user.id
                )
            )
        )
    )
    conversation = result.scalar()

    if not conversation:
        conversation = Conversation(
            user1_id=current_user.id,
            user2_id=receiver.id,
            created_at=now,
            last_message_at=now
        )
        db.add(conversation)
        await db.flush()

    # 创建新消息
    new_message = Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        content=message.content,
        created_at=now
    )
    db.add(new_message)

    # 更新会话的最后消息时间
    conversation.last_message_at = now

    try:
        await db.commit()
        await db.refresh(new_message)
        return {
            "message": "发送成功",
            "conversation_id": conversation.id,
            "message_id": new_message.id,
            "created_at": new_message.created_at.isoformat()
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送消息失败: {str(e)}"
        )

@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    limit: int = 20,
    before_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取会话消息记录"""
    # 验证用户是否是会话参与者
    result = await db.execute(
        select(Conversation).where(
            and_(
                Conversation.id == conversation_id,
                or_(
                    Conversation.user1_id == current_user.id,
                    Conversation.user2_id == current_user.id
                )
            )
        )
    )
    conversation = result.scalar()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此会话"
        )

    # 构建消息查询
    query = (
        select(Message, User)
        .join(User, Message.sender_id == User.id)
        .where(Message.conversation_id == conversation_id)
    )
    
    if before_id:
        query = query.where(Message.id < before_id)
    
    query = query.order_by(desc(Message.created_at)).limit(limit)
    
    result = await db.execute(query)
    messages = result.all()

    # 标记消息为已读
    now = datetime.now(timezone.utc)
    for msg, _ in messages:
        if msg.sender_id != current_user.id and not msg.is_read:
            msg.is_read = True
            msg.read_at = now

    await db.commit()

    return [
        {
            "id": msg.id,
            "sender": {
                "id": user.id,
                "username": user.username
            },
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "is_read": msg.is_read,
            "read_at": msg.read_at.isoformat() if msg.read_at else None
        }
        for msg, user in messages
    ]

@router.delete("/messages/{message_id}")
async def recall_message(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """撤回消息（仅限2分钟内的自己发送的消息）"""
    try:
        # 查找消息
        result = await db.execute(
            select(Message)
            .where(Message.id == message_id)
        )
        message = result.scalar()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="消息不存在"
            )
        
        # 检查是否是自己发送的消息
        if message.sender_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只能撤回自己发送的消息"
            )
        
        # 确保消息创建时间有时区信息
        message_time = message.created_at
        if message_time.tzinfo is None:
            message_time = message_time.replace(tzinfo=timezone.utc)
        
        # 检查是否在2分钟内
        current_time = datetime.now(timezone.utc)
        time_diff = current_time - message_time
        
        if time_diff > timedelta(minutes=2):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只能撤回2分钟内的消息"
            )
        
        # 删除消息
        await db.delete(message)
        await db.commit()
        
        return {
            "message": "消息已撤回",
            "message_id": message_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"撤回消息失败: {str(e)}"
        )

@router.post("/messages/search")
async def search_messages(
    search: MessageSearch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """搜索聊天记录"""
    try:
        # 验证会话权限
        result = await db.execute(
            select(Conversation).where(
                and_(
                    Conversation.id == search.conversation_id,
                    or_(
                        Conversation.user1_id == current_user.id,
                        Conversation.user2_id == current_user.id
                    )
                )
            )
        )
        conversation = result.scalar()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此会话"
            )
        
        # 搜索消息
        result = await db.execute(
            select(Message, User)
            .join(User, Message.sender_id == User.id)
            .where(
                and_(
                    Message.conversation_id == search.conversation_id,
                    Message.content.ilike(f"%{search.content}%")
                )
            )
            .order_by(desc(Message.created_at))
        )
        messages = result.all()
        
        return {
            "message": "搜索成功",
            "results": [
                {
                    "id": message.id,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                    "is_read": message.is_read,
                    "sender": {
                        "id": user.id,
                        "username": user.username
                    }
                }
                for message, user in messages
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索消息失败: {str(e)}"
        )
