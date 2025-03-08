from colorama import init, Fore, Style
from playwright.async_api import async_playwright
import asyncio
from fastapi import APIRouter

# 创建路由
router = APIRouter(tags=["weather"])

# 初始化 colorama
init(autoreset=True)

class Logger:
    @staticmethod
    def info(message):
        print(f"{Fore.GREEN}[INFO] {message}{Style.RESET_ALL}")
    
    @staticmethod
    def error(message):
        print(f"{Fore.RED}[ERROR] {message}{Style.RESET_ALL}")
    
    @staticmethod
    def warning(message):
        print(f"{Fore.YELLOW}[WARNING] {message}{Style.RESET_ALL}")
    
    @staticmethod
    def debug(message):
        print(f"{Fore.BLUE}[DEBUG] {message}{Style.RESET_ALL}")

class Weather:
    """天气信息抓取类"""
    
    def __init__(self):
        self.logger = Logger()
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
    
    async def initialize(self):
        """初始化Playwright资源"""
        try:
            # 在Windows环境下设置正确的事件循环
            import platform
            if platform.system() == 'Windows':
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if not isinstance(loop, asyncio.ProactorEventLoop):
                        asyncio.set_event_loop(asyncio.ProactorEventLoop())
                        self.logger.info("已设置ProactorEventLoop用于Windows环境")
                except RuntimeError:
                    # 如果当前线程没有事件循环
                    loop = asyncio.ProactorEventLoop()
                    asyncio.set_event_loop(loop)
                    self.logger.info("已为当前线程创建新的ProactorEventLoop")
            
            # 尝试启动Playwright
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.playwright = await async_playwright().start()
                    self.browser = await self.playwright.chromium.launch(headless=True)
                    self.context = await self.browser.new_context()
                    self.page = await self.context.new_page()
                    self.logger.info("Playwright资源初始化成功")
                    return
                except Exception as e:
                    self.logger.error(f"初始化尝试 {attempt+1}/{max_retries} 失败: {e}")
                    if attempt < max_retries - 1:
                        # 等待一段时间后重试
                        await asyncio.sleep(1)
                    else:
                        raise
        except Exception as e:
            self.logger.error(f"初始化Playwright资源时发生错误: {e}")
            await self.close()
    
    async def navigate_to_page(self, url="https://www.msn.cn/zh-cn/weather/hourlyforecast/"):
        """导航到天气页面"""
        try:
            await self.page.goto(url)
            self.logger.info(f"成功导航到: {url}")
            # 等待页面加载
            await self.page.wait_for_load_state("networkidle")
        except Exception as e:
            self.logger.error(f"导航到页面时发生错误: {e}")
    
    async def get_city_name(self):
        """获取城市名称"""
        try:
            # 等待城市名称元素加载
            city_element = await self.page.query_selector(".fullNameLink-DS-EOqGMX")
            if city_element:
                city_name = await city_element.inner_text()
                city_name = city_name.replace(",", "")
                city_name = city_name.replace(" ", "")
                self.logger.info(f"获取到城市名称: {city_name}")
                return city_name
            else:
                self.logger.error("未找到城市名称元素")
                return None
        except Exception as e:
            self.logger.error(f"获取城市名称时发生错误: {e}")
            return None
    
    async def get_weather_data(self):
        """获取第一条天气信息"""
        try:
            # 自动导航到目标页面
            await self.navigate_to_page()

            # 获取第一个 hourlyItem 元素
            hourly_item = await self.page.query_selector(".mainRow-DS-pbdUFF")
            if not hourly_item:
                self.logger.error("未找到第一条天气信息元素")
                return None

            # 提取时间
            time_element = await hourly_item.query_selector(".timeItem-DS-hFPfcz span")
            time = await time_element.inner_text() if time_element else "未知"

            # 提取天气状况
            weather_condition_element = await hourly_item.query_selector(".captureItem-DS-BM8Vzt span")
            weather_condition = await weather_condition_element.inner_text() if weather_condition_element else "未知"

            # 提取温度
            temperature_element = await hourly_item.query_selector(".rowInfoItem-DS-hTwXE3 .rowItemText-DS-cwphqS")
            temperature = await temperature_element.inner_text() if temperature_element else "未知"

            # 提取体感温度
            feels_like_element = await hourly_item.query_selector(".itemLabel-DS-EtLmOv:has-text('体感温度') + .itemValue-DS-hGqBrX")
            feels_like = await feels_like_element.inner_text() if feels_like_element else "未知"

            # 提取云量
            cloud_cover_element = await hourly_item.query_selector(".itemLabel-DS-EtLmOv:has-text('云量') + .itemValue-DS-hGqBrX")
            cloud_cover = await cloud_cover_element.inner_text() if cloud_cover_element else "未知"

            # 提取露点
            dew_point_element = await hourly_item.query_selector(".itemLabel-DS-EtLmOv:has-text('露点') + .itemValue-DS-hGqBrX")
            dew_point = await dew_point_element.inner_text() if dew_point_element else "未知"

            # 提取湿度
            humidity_element = await hourly_item.query_selector(".itemLabel-DS-EtLmOv:has-text('湿度') + .itemValue-DS-hGqBrX")
            humidity = await humidity_element.inner_text() if humidity_element else "未知"

            # 提取风速
            wind_element = await hourly_item.query_selector(".itemLabel-DS-EtLmOv:has-text('风') + .itemValue-DS-hGqBrX")
            wind = await wind_element.inner_text() if wind_element else "未知"

            # 提取气压
            pressure_element = await hourly_item.query_selector(".itemLabel-DS-EtLmOv:has-text('气压') + .itemValue-DS-hGqBrX")
            pressure = await pressure_element.inner_text() if pressure_element else "未知"

            # 提取能见度
            visibility_element = await hourly_item.query_selector(".itemLabel-DS-EtLmOv:has-text('可见性') + .itemValue-DS-hGqBrX")
            visibility = await visibility_element.inner_text() if visibility_element else "未知"

            # 获取城市名称
            city_name = await self.get_city_name()

            # 构建天气数据
            weather_data = {
                "city": city_name or "未知城市",
                "time": time,
                "condition": weather_condition,
                "temperature": temperature,
                "feels_like": feels_like,
                "cloud_cover": cloud_cover,
                "dew_point": dew_point,
                "humidity": humidity,
                "wind": wind,
                "pressure": pressure,
                "visibility": visibility
            }

            # 数据清洗和标准化
            self._clean_weather_data(weather_data)

            self.logger.info(f"获取天气数据成功: {weather_data}")
            return weather_data
        except Exception as e:
            self.logger.error(f"获取天气数据时发生错误: {e}")
            return {"error": str(e)}
    
    def _clean_weather_data(self, data):
        """清洗和标准化天气数据"""
        try:
            # 处理城市名称
            if "city" in data and data["city"]:
                # 移除多余空格并保留中文
                data["city"] = data["city"].strip()
            
            # 处理温度
            if "temperature" in data and data["temperature"]:
                # 提取数字部分
                temp = data["temperature"].strip()
                # 移除空格并确保用°C表示
                if "°" in temp:
                    temp = temp.replace(" ", "")
                    if not temp.endswith("C") and not temp.endswith("c"):
                        temp = temp.rstrip("°") + "°C"
                data["temperature"] = temp
            
            # 处理体感温度
            if "feels_like" in data and data["feels_like"]:
                feels = data["feels_like"].strip()
                if "°" in feels:
                    feels = feels.replace(" ", "")
                    if not feels.endswith("C") and not feels.endswith("c"):
                        feels = feels.rstrip("°") + "°C"
                data["feels_like"] = feels

            # 处理云量
            if "cloud_cover" in data and data["cloud_cover"]:
                cloud = data["cloud_cover"].strip()
                if not cloud.endswith("%"):
                    cloud = cloud + "%"
                data["cloud_cover"] = cloud 
            
            # 处理露点
            if "dew_point" in data and data["dew_point"]:
                dew = data["dew_point"].strip()
                if "°" in dew:
                    dew = dew.replace(" ", "")
                    if not dew.endswith("C") and not dew.endswith("c"):
                        dew = dew.rstrip("°") + "°C"
                data["dew_point"] = dew
            
            # 处理湿度
            if "humidity" in data and data["humidity"]:
                # 确保湿度值以%结尾
                hum = data["humidity"].strip()
                if not hum.endswith("%"):
                    # 尝试提取数字
                    import re
                    match = re.search(r"(\d+)", hum)
                    if match:
                        hum = match.group(1) + "%"
                data["humidity"] = hum
            
            # 处理风速
            if "wind" in data and data["wind"]:
                # 保持风速值不变，只去除空格
                data["wind"] = data["wind"].strip()
            
            # 处理气压
            if "pressure" in data and data["pressure"]:
                # 确保气压值以hPa结尾
                pres = data["pressure"].strip()
                if "hPa" not in pres:
                    # 尝试提取数字
                    import re
                    match = re.search(r"(\d+)", pres)
                    if match:
                        pres = match.group(1) + " hPa"
                data["pressure"] = pres
            
            # 确保所有字符串值都是Unicode字符串
            for key, value in data.items():
                if isinstance(value, str):
                    # 确保值是Unicode字符串
                    data[key] = value
        except Exception as e:
            self.logger.error(f"清洗数据时出错: {e}")
            # 出错时不修改数据
    
    async def close(self):
        """关闭Playwright资源"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self.logger.info("Playwright资源已关闭")
        except Exception as e:
            self.logger.error(f"关闭Playwright资源时发生错误: {e}")

async def run_tests():
    """运行测试"""
    weather = Weather()
    await weather.initialize()
    weather_data = await weather.get_weather_data()
    print("天气数据:", weather_data)
    await weather.close()

# API路由
@router.get("/weather")
async def get_weather():
    """获取当前天气信息"""
    try:
        weather = Weather()
        await weather.initialize()
        weather_data = await weather.get_weather_data()
        await weather.close()
        return {"status": "success", "data": weather_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
# 如果直接运行文件，则执行测试
if __name__ == "__main__":
    import asyncio
    asyncio.run(run_tests())