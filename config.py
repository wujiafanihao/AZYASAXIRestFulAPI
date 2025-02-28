"""
配置模块
存储应用程序的配置变量
"""
import secrets

# JWT配置
SECRET_KEY = secrets.token_urlsafe(32)  # 生成安全的随机密钥
ALGORITHM = "HS256"  # JWT加密算法
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # 访问令牌过期时间（分钟）
