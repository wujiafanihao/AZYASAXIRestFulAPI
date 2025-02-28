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

class UserListAccess(BaseModel):
    """用户列表访问请求模型"""
    root: str

# API路由
@router.post("/users/all")
async def get_all_users(
    request: UserListAccess,
    db: AsyncSession = Depends(get_db)
):
    """获取所有用户列表（包含其好友信息、在线状态和用户资料）"""
    if request.root != "azyasaxi":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无访问权限"
        )
    
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
            "email": user.email,
            "profile": {
                "avatar_url": profile.avatar_url if profile else None,
                "background_url": profile.background_url if profile else None,
                "gender": profile.gender if profile else None,
                "bio": profile.bio if profile else None
            } if profile else None,
            "online_status": {
                "is_online": user.is_online,
                "last_active": user.last_active.isoformat() if user.last_active else None,
                "access_token": user.current_token if user.is_online else None
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

@router.get("/users/profile")
async def get_user_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的资料"""
    result = await db.execute(
        select(UserProfile)
        .where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalars().first()
    
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
        },
        "profile": {
            "avatar_url": profile.avatar_url if profile else None,
            "background_url": profile.background_url if profile else None,
            "gender": profile.gender if profile else None,
            "bio": profile.bio if profile else None
        } if profile else None
    }

@router.put("/users/profile")
async def update_user_profile(
    profile_update: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新当前用户的资料"""
    try:
        # 查找现有的用户资料
        result = await db.execute(
            select(UserProfile)
            .where(UserProfile.user_id == current_user.id)
        )
        profile = result.scalars().first()
        
        if profile:
            # 更新现有资料
            if profile_update.bio is not None:
                profile.bio = profile_update.bio
            if profile_update.avatar_url is not None:
                profile.avatar_url = profile_update.avatar_url
            if profile_update.background_url is not None:
                profile.background_url = profile_update.background_url
            if profile_update.gender is not None:
                profile.gender = profile_update.gender
        else:
            # 创建新的用户资料
            profile = UserProfile(
                user_id=current_user.id,
                bio=profile_update.bio,
                avatar_url=profile_update.avatar_url,
                background_url=profile_update.background_url,
                gender=profile_update.gender
            )
            db.add(profile)
        
        await db.commit()
        await db.refresh(profile)
        
        return {
            "message": "资料更新成功",
            "profile": {
                "avatar_url": profile.avatar_url,
                "background_url": profile.background_url,
                "gender": profile.gender,
                "bio": profile.bio
            }
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新资料失败: {str(e)}"
        )

@router.get("/users/search")
async def search_users(
    query: str,
    db: AsyncSession = Depends(get_db)
):
    """搜索用户（通过用户名或邮箱）"""
    try:
        result = await db.execute(
            select(User, UserProfile)
            .outerjoin(UserProfile)
            .where(
                or_(
                    User.username.ilike(f"%{query}%"),
                    User.email.ilike(f"%{query}%")
                )
            )
        )
        users = result.all()
        
        if not users:
            return {
                "message": "未找到匹配的用户",
                "users": []
            }
        
        return {
            "message": "查询成功",
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "profile": {
                        "avatar_url": profile.avatar_url if profile else None,
                        "gender": profile.gender if profile else None
                    } if profile else None
                }
                for user, profile in users
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索用户失败: {str(e)}"
        )

@router.get("/users/info/{query}")
async def get_user_info(
    query: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定用户的详细信息（仅限好友）"""
    try:
        # 查找目标用户
        result = await db.execute(
            select(User, UserProfile)
            .outerjoin(UserProfile)
            .where(
                or_(
                    User.username == query,
                    User.email == query
                )
            )
        )
        user_info = result.first()
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
            
        target_user, target_profile = user_info
        
        # 检查是否为好友关系
        result = await db.execute(
            select(Friendship).where(
                or_(
                    and_(
                        Friendship.user_id == current_user.id,
                        Friendship.friend_id == target_user.id
                    ),
                    and_(
                        Friendship.user_id == target_user.id,
                        Friendship.friend_id == current_user.id
                    )
                )
            )
        )
        
        if not result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只能查看好友的详细信息"
            )
        
        # 获取目标用户的好友列表
        friend_result = await db.execute(
            select(User)
            .join(Friendship, User.id == Friendship.friend_id)
            .where(Friendship.user_id == target_user.id)
        )
        friends = friend_result.scalars().all()
        
        return {
            "message": "查询成功",
            "user": {
                "id": target_user.id,
                "username": target_user.username,
                "email": target_user.email,
                "profile": {
                    "avatar_url": target_profile.avatar_url if target_profile else None,
                    "background_url": target_profile.background_url if target_profile else None,
                    "gender": target_profile.gender if target_profile else None,
                    "bio": target_profile.bio if target_profile else None
                } if target_profile else None,
                "online_status": {
                    "is_online": target_user.is_online,
                    "last_active": target_user.last_active.isoformat() if target_user.last_active else None
                },
                "friends": [
                    {
                        "id": friend.id,
                        "username": friend.username
                    }
                    for friend in friends
                ]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户信息失败: {str(e)}"
        )
