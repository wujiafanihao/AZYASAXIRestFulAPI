from typing import List, Dict, Callable, Optional
from fastapi import APIRouter
from AIservices.weather import Weather
import asyncio
import platform

# 创建路由
router = APIRouter(tags=["tools"])

# 定义工具类
class Tool:
    def __init__(self, name: str, description: str, function: Callable):
        self.name = name
        self.description = description
        self.function = function
        self.is_async = False

    def __call__(self, *args, **kwargs):
        return self.function(*args, **kwargs)

# 异步工具类
class AsyncTool(Tool):
    def __init__(self, name: str, description: str, function: Callable):
        super().__init__(name, description, function)
        self.is_async = True

# 工具管理器类
class ToolManager:
    def __init__(self):
        self.tools: Dict[str, Tool] = {} # 工具字典
        self._initialize_tools()
    
    def _initialize_tools(self):
        """初始化所有可用工具"""
        self._register_weather_tool()
    
    def _register_weather_tool(self):
        """注册天气工具"""
        try:
            async def get_weather():
                weather = Weather()
                await weather.initialize()
                try:
                    data = await weather.get_weather_data()
                    return data
                finally:
                    await weather.close()

            weather_tool = AsyncTool(
                name="weather",
                description="获取天气信息",
                function=get_weather
            )
            self.tools["weather"] = weather_tool
        except Exception as e:
            print(f"注册天气工具失败: {e}")
    
    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self.tools.keys())
    
    def get_tool_descriptions(self) -> Dict[str, str]:
        """获取所有工具描述"""
        return {name: tool.description for name, tool in self.tools.items()}
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """获取指定名称的工具"""
        return self.tools.get(name)
    
    def execute_tool(self, name: str, *args, **kwargs):
        """执行指定名称的工具（支持同步和异步工具）"""
        tool = self.get_tool(name)
        if not tool:
            return None
        
        # 检查是否是异步工具
        if isinstance(tool, AsyncTool):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # 如果当前线程没有事件循环，则创建一个新的
                if platform.system() == 'Windows':
                    # 在Windows上使用ProactorEventLoop
                    loop = asyncio.ProactorEventLoop()
                else:
                    loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(tool.function(*args, **kwargs))
        else:
            return tool.function(*args, **kwargs)
    
    def should_use_tool(self, message: str) -> Optional[str]:
        """根据用户消息判断是否应该使用工具，并返回工具名称"""
        if "天气" in message or "weather" in message.lower():
            return "weather"
        return None

# 创建全局工具管理器实例
tool_manager = ToolManager()

# 工具API路由
@router.get("/tools/list")
def list_tools():
    """获取所有可用工具列表"""
    return {
        "tools": tool_manager.get_tool_names(),
        "descriptions": tool_manager.get_tool_descriptions()
    }

@router.post("/tools/{tool_name}/execute")
def execute_tool(tool_name: str):
    """执行指定的工具"""
    tool = tool_manager.get_tool(tool_name)
    if not tool:
        return {"error": f"工具 '{tool_name}' 不存在"}
    
    try:
        result = tool_manager.execute_tool(tool_name)
        return {
            "tool": tool_name,
            "result": result
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    manager = ToolManager()
    print(f"可用工具列表: {manager.get_tool_names()}")
    print(f"工具描述: {manager.get_tool_descriptions()}")
    
    weather_data = manager.execute_tool("weather")
    print(f"天气数据: {weather_data}")
    
    test_message = "今天的天气怎么样？"
    tool_name = manager.should_use_tool(test_message)
    print(f"消息 '{test_message}' 应该使用工具: {tool_name}")