from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from dependencies import get_db, get_current_user
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from datetime import datetime, timezone
from pydantic import BaseModel
import os

load_dotenv()

router = APIRouter(tags=["azyasaxiAI"])

# 定义请求模型
class RequestModel(BaseModel):
    # userId: str
    # memoryId : str
    # userName: str
    message: str

class AzyasaxiAI:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.getenv("MODEL"),
            temperature=float(os.getenv("TEMPERATURE")),  # 转换为浮点数
            api_key=os.getenv("API_KEY"),
            base_url=os.getenv("BASE_URL"),
        )

    def generate_response(self, message: str) -> str:
        return self.llm.invoke(message).content

# API路由
@router.post("/chat/completions")
def chat_completions(
    request: RequestModel,
    # db: AsyncSession = Depends(get_db)
):
    try:
        azyasaxi = AzyasaxiAI()
        response = azyasaxi.generate_response(request.message)
        return {
            "useTool": "normal",
            "SessionId": None,
            "memoryIid": None,
            "response": response,
            "LastMessageTime": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"error": str(e)}
     

