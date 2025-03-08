"""
API服务
提供AI聊天服务和工具选择功能
"""

import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependencies import get_db, get_current_user
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from models import User
import asyncio
from AIservices.tools import tool_manager
from AIservices.session import session_manager
from AIservices.chat_history import chat_history_manager

load_dotenv()

router = APIRouter(tags=["azyasaxiAI"])

# 定义请求模型
class RequestModel(BaseModel):
    message: str

class ChatHistoryResponse(BaseModel):
    session_id: str
    history: List[Dict]

class AzyasaxiAI:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.getenv("MODEL"),
            temperature=float(os.getenv("TEMPERATURE")),
            api_key=os.getenv("API_KEY"),
            base_url=os.getenv("BASE_URL"),
        )
    
    def generate_response(self, message: str, history: List[Dict] = None) -> str:
        """生成回复，支持历史记录上下文"""
        if not history:
            # 如果没有历史记录，直接调用LLM
            return self.llm.invoke(message).content
        
        # 构建消息列表，包含系统消息和历史记录
        messages = [
            SystemMessage(content="You are a helpful AI assistant that can remember conversation history and provide consistent responses. You can use various tools to help the user.")
        ]
        
        # 添加历史记录（最多5条，避免上下文过长）
        for item in history[-5:]:
            messages.append(HumanMessage(content=item["user_message"]))
            messages.append(AIMessage(content=item["ai_response"]))
        
        # 添加当前用户消息
        messages.append(HumanMessage(content=message))
        
        # 调用LLM生成回复
        return self.llm.invoke(messages).content
    
    def should_use_tool(self, message: str) -> Optional[str]:
        """判断是否应该使用工具"""
        return tool_manager.should_use_tool(message)
    
    async def execute_tool(self, tool_name: str, *args, **kwargs) -> Dict[str, Any]:
        """执行指定工具"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 如果当前线程没有事件循环，则创建一个新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = await loop.run_in_executor(
            None, lambda: tool_manager.execute_tool(tool_name, *args, **kwargs)
        )
        # 构建工具执行结果
        return {
            "tool_name": tool_name,
            "result": result
        }

# API路由
@router.post("/chat/completions")
async def chat_completions(
    request: RequestModel,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # 获取用户信息
        username = current_user.username
        user_id = current_user.id
        
        # 获取或创建会话ID，关联用户ID（现在是异步的，需要传入db）
        session_id = await session_manager.get_session_id(username, user_id, db)
        
        # 获取聊天历史记录
        history = await chat_history_manager.load_from_db(db, user_id, session_id)
        
        # 创建AI实例
        azyasaxi = AzyasaxiAI()
        
        # 检查是否应该使用工具
        tool_name = azyasaxi.should_use_tool(request.message)
        
        if tool_name:
            # 使用工具生成响应
            tool_result = await azyasaxi.execute_tool(tool_name)
            
            # 构建包含工具结果的消息列表
            messages = [
                SystemMessage(content="你是一个有用的AI助手，能够记住对话历史并提供连贯的回复。你可以使用各种工具来帮助用户。")
            ]
            
            # 添加历史记录（最多5条，避免上下文过长）
            for item in history[-5:]:
                messages.append(HumanMessage(content=item["user_message"]))
                messages.append(AIMessage(content=item["ai_response"]))
            
            # 添加当前用户消息和工具结果
            tool_info = f"工具名称: {tool_name}\n工具结果: {tool_result['result']}"
            messages.append(HumanMessage(content=request.message))
            messages.append(SystemMessage(content=f"你使用了{tool_name}工具，获取到以下信息：\n{tool_result['result']}\n请基于这些信息回答用户的问题。"))
            
            # 调用LLM生成回复
            response = azyasaxi.llm.invoke(messages).content
            use_tool = tool_name
        else:
            # 正常聊天，传入历史记录
            response = azyasaxi.generate_response(request.message, history=history)
            use_tool = "normal"
        
        # 记录聊天历史（内存）
        chat_history_manager.add_message(
            session_id=session_id,
            user_message=request.message,
            ai_response=response,
            tool_used=use_tool if use_tool != "normal" else None
        )
        
        # 记录聊天历史（数据库）
        await chat_history_manager.save_to_db(
            db=db,
            user_id=user_id,
            session_id=session_id,
            user_message=request.message,
            ai_response=response,
            tool_used=use_tool if use_tool != "normal" else None
        )
        
        return {
            "useTool": use_tool,
            "SessionId": session_id,
            "response": response,
            "LastMessageTime": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        return {"error": str(e)}

# 获取聊天历史
@router.get("/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # 获取用户信息
        username = current_user.username
        user_id = current_user.id
        
        # 获取会话ID（现在是异步的，需要传入db）
        session_id = await session_manager.get_session_id(username, user_id, db)
        
        # 从数据库加载聊天历史
        history = await chat_history_manager.load_from_db(db, user_id, session_id)
        
        return {
            "session_id": session_id,
            "history": history
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        return {"error": str(e)}

# 清除聊天历史
@router.delete("/chat/history")
async def clear_chat_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # 获取用户信息
        username = current_user.username
        user_id = current_user.id
        
        # 获取会话ID（现在是异步的，需要传入db）
        session_id = await session_manager.get_session_id(username, user_id, db)
        
        # 清除数据库中的聊天历史
        success = await chat_history_manager.clear_db_history(db, user_id, session_id)
        
        if success:
            return {"message": "聊天历史已清除"}
        else:
            return {"message": "未找到聊天历史"}
    except HTTPException as e:
        raise e
    except Exception as e:
        return {"error": str(e)}
     

