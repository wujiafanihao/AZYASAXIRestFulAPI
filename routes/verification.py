"""
验证码模块
处理邮箱验证码的生成和验证
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import random
import asyncio
from concurrent.futures import ThreadPoolExecutor

from models import User
from dependencies import get_db

# 创建路由器
router = APIRouter(tags=["验证码"])

# 创建线程池执行器
executor = ThreadPoolExecutor()

# 内存中存储验证码及其过期时间
# 结构: {email: {"code": "123456", "expiry_time": datetime}}
verification_codes = {}

class EmailRequest(BaseModel):
    """邮箱请求模型"""
    email: str

async def generate_and_return_code(email: str) -> str:
    """
    生成并返回验证码
    :param email: 用户邮箱
    :return: 生成的6位数字验证码
    """
    # 使用事件循环在线程池中生成随机验证码
    loop = asyncio.get_event_loop()
    code = await loop.run_in_executor(
        executor,
        lambda: "".join(random.choices("0123456789", k=6))
    )
    
    # 设置验证码过期时间（1分钟）
    expiry_time = datetime.now(timezone.utc) + timedelta(minutes=1)
    
    # 存储验证码信息
    verification_codes[email] = {
        "code": code,
        "expiry_time": expiry_time
    }
    
    print(f"验证码已生成: {code}, 请求邮箱为：{email}")
    return code

def verify_code(email: str, code: str) -> bool:
    """
    验证邮箱验证码
    :param email: 用户邮箱
    :param code: 用户提供的验证码
    :return: 验证码是否有效
    """
    # 检查邮箱是否有验证码记录
    if email not in verification_codes or not verification_codes[email]["code"]:
        return False
    
    # 检查验证码是否过期
    if verification_codes[email]["expiry_time"] < datetime.now(timezone.utc):
        del verification_codes[email]
        return False
    
    # 检查验证码是否匹配
    return code == verification_codes[email]["code"]

def clear_verification_code(email: str) -> None:
    """
    清理验证码
    :param email: 用户邮箱
    """
    if email in verification_codes:
        del verification_codes[email]

@router.post("/get_verification_code")
async def get_verification_code(request: EmailRequest, db: AsyncSession = Depends(get_db)):
    """
    获取验证码接口
    :param request: 包含email的请求
    :param db: 数据库会话
    :return: 包含验证码的响应
    """
    # 检查邮箱是否已注册
    result = await db.execute(
        select(User).where(User.email.ilike(request.email))
    )
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已注册",
        )
    
    # 生成验证码
    code = await generate_and_return_code(request.email)
    
    # 返回验证码（在实际生产环境中，应该通过邮件发送而不是直接返回）
    return {
        "message": "验证码已生成",
        "code": code,
        "Email": request.email
    }
