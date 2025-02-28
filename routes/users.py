"""
用户模块
处理用户相关的路由，包括用户资料和好友关系
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from models import User, UserProfile, FriendRequest, Friendship
from dependencies import get_current_user, get_db

# 创建路由器
router = APIRouter(tags=["用户"])

# 请求模型
class UserProfileUpdate(BaseModel):
    """用户资料更新请求模型"""
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    background_url: Optional[str] = None
    gender: Optional[str] = None

class FriendRequestCreate(BaseModel):
    """好友申请创建请求模型"""
    username: Optional[str] = None
    email: Optional[str] = None

class FriendRequestAction(BaseModel):
    """好友申请处理请求模型"""
    action: str  # accept or reject

# API路由
@router.get("/users/all")
async def get_all_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有用户列表（包含其好友信息）"""
    result = await db.execute(
        select(User, UserProfile)
        .outerjoin(UserProfile)
    )
    users = result.all()
    
    # 获取每个用户的好友列表
    user_friends = {}
    for user, _ in users:
        friend_result = await db.execute(
            select(User)
            .join(Friendship, User.id == Friendship.friend_id)
            .where(Friendship.user_id == user.id)
        )
        friends = friend_result.scalars().all()
        user_friends[user.id] = [
            {"id": friend.id, "username": friend.username}
            for friend in friends
        ]
    
    return [
        {
            "id": user.id,
            "username": user.username,
            "profile": {
                "avatar_url": profile.avatar_url if profile else None,
            },
            "friends": user_friends.get(user.id, [])
        }
        for user, profile in users
    ]

@router.get("/users/friends")
async def get_friends(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的好友列表"""
    result = await db.execute(
        select(User, UserProfile)
        .outerjoin(UserProfile)
        .join(Friendship, User.id == Friendship.friend_id)
        .where(Friendship.user_id == current_user.id)
    )
    friends = result.all()
    
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "profile": {
                "avatar_url": profile.avatar_url if profile else None,
                "bio": profile.bio if profile else None,
                "gender": profile.gender if profile else None
            }
        }
        for user, profile in friends
    ]

class FriendListAccess(BaseModel):
    """好友列表访问请求模型"""
    root: str

class UserIdentifier(BaseModel):
    """用户标识请求模型"""
    identifier: str  # 用户名或邮箱
    root: str

@router.post("/get_user_friends", dependencies=[])
async def get_user_friends(
    user_info: UserIdentifier,
    db: AsyncSession = Depends(get_db)
):
    """获取指定用户的好友列表"""
    # 验证访问权限
    if user_info.root != "azyasaxi":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无访问权限"
        )

    # 查找用户（支持用户名或邮箱）
    result = await db.execute(
        select(User).where(
            or_(
                User.username == user_info.identifier,
                User.email == user_info.identifier
            )
        )
    )
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 获取该用户的好友列表
    result = await db.execute(
        select(User, UserProfile)
        .outerjoin(UserProfile)
        .join(Friendship, User.id == Friendship.friend_id)
        .where(Friendship.user_id == user.id)
    )
    friends = result.all()
    
    return [
        {
            "id": friend.id,
            "username": friend.username,
            "email": friend.email,
            "profile": {
                "avatar_url": profile.avatar_url if profile else None,
                "bio": profile.bio if profile else None,
                "gender": profile.gender if profile else None
            }
        }
        for friend, profile in friends
    ]

# 获取好友申请列表
@router.get("/friend-requests")
async def get_friend_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的好友申请列表"""
    # 获取收到的申请
    received_result = await db.execute(
        select(FriendRequest, User, UserProfile)
        .join(User, FriendRequest.sender_id == User.id)
        .outerjoin(UserProfile, User.id == UserProfile.user_id)
        .where(
            and_(
                FriendRequest.receiver_id == current_user.id,
                FriendRequest.status == "pending"
            )
        )
    )
    received = received_result.all()

    # 获取发送的申请
    sent_result = await db.execute(
        select(FriendRequest, User, UserProfile)
        .join(User, FriendRequest.receiver_id == User.id)
        .outerjoin(UserProfile, User.id == UserProfile.user_id)
        .where(
            and_(
                FriendRequest.sender_id == current_user.id,
                FriendRequest.status == "pending"
            )
        )
    )
    sent = sent_result.all()

    return {
        "received": [
            {
                "request_id": req.id,
                "sender": {
                    "id": user.id,
                    "username": user.username,
                    "avatar_url": profile.avatar_url if profile else None
                },
                "status": req.status,
                "created_at": req.created_at
            }
            for req, user, profile in received
        ],
        "sent": [
            {
                "request_id": req.id,
                "receiver": {
                    "id": user.id,
                    "username": user.username,
                    "avatar_url": profile.avatar_url if profile else None
                },
                "status": req.status,
                "created_at": req.created_at
            }
            for req, user, profile in sent
        ]
    }

@router.post("/friend-requests")
async def create_friend_request(
    request: FriendRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """发送好友申请"""
    if not request.username and not request.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须提供用户名或邮箱"
        )

    # 查找接收者
    query = select(User)
    if request.username:
        query = query.where(User.username == request.username)
    else:
        query = query.where(User.email == request.email)

    result = await db.execute(query)
    receiver = result.scalars().first()

    if not receiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    if receiver.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能添加自己为好友"
        )

    # 检查是否已经是好友
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
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已经是好友关系"
        )
    
    # 检查是否已经有待处理的申请
    result = await db.execute(
        select(FriendRequest).where(
            and_(
                FriendRequest.sender_id == current_user.id,
                FriendRequest.receiver_id == receiver.id,
                FriendRequest.status == "pending"
            )
        )
    )
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已经发送过好友申请"
        )
    
    # 创建好友申请
    friend_request = FriendRequest(
        sender_id=current_user.id,
        receiver_id=receiver.id,
        status="pending"
    )
    
    try:
        db.add(friend_request)
        await db.commit()
        await db.refresh(friend_request)
        return {
            "message": "好友申请已发送",
            "request_id": friend_request.id,
            "receiver": {
                "id": receiver.id,
                "username": receiver.username
            }
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送申请失败: {str(e)}"
        )

@router.put("/friend-requests/{request_id}")
async def handle_friend_request(
    request_id: int,
    action: FriendRequestAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """处理好友申请"""
    # 获取好友申请
    result = await db.execute(
        select(FriendRequest).where(
            and_(
                FriendRequest.id == request_id,
                FriendRequest.receiver_id == current_user.id,
                FriendRequest.status == "pending"
            )
        )
    )
    friend_request = result.scalars().first()
    
    if not friend_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="好友申请不存在或已处理"
        )
    
    if action.action not in ["accept", "reject"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的操作"
        )
    
    try:
        friend_request.status = action.action
        
        if action.action == "accept":
            # 创建好友关系
            friendship1 = Friendship(
                user_id=friend_request.sender_id,
                friend_id=friend_request.receiver_id
            )
            friendship2 = Friendship(
                user_id=friend_request.receiver_id,
                friend_id=friend_request.sender_id
            )
            db.add(friendship1)
            db.add(friendship2)
        
        await db.commit()
        return {"message": f"好友申请已{action.action}"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理申请失败: {str(e)}"
        )

@router.delete("/friends/{username}")
async def delete_friend(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除好友"""
    try:
        # 查找要删除的好友
        result = await db.execute(
            select(User).where(User.username == username)
        )
        friend = result.scalars().first()
        if not friend:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        # 检查是否为好友关系
        result = await db.execute(
            select(Friendship).where(
                or_(
                    and_(
                        Friendship.user_id == current_user.id,
                        Friendship.friend_id == friend.id
                    ),
                    and_(
                        Friendship.user_id == friend.id,
                        Friendship.friend_id == current_user.id
                    )
                )
            )
        )
        if not result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该用户不是你的好友"
            )

        # 删除双向好友关系
        await db.execute(
            Friendship.__table__.delete().where(
                or_(
                    and_(
                        Friendship.user_id == current_user.id,
                        Friendship.friend_id == friend.id
                    ),
                    and_(
                        Friendship.user_id == friend.id,
                        Friendship.friend_id == current_user.id
                    )
                )
            )
        )
        await db.commit()
        return {"message": "好友删除成功"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除好友失败: {str(e)}"
        )
