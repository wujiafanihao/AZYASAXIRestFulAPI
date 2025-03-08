# Restful API 

本项目是一个基于FastAPI的RESTful API系统，提供用户认证和项目管理功能。

## API端点

### 项目列表API

| 方法   | 路径                      | 描述                 |
|--------|---------------------------|---------------------|
| POST   | /api/v1/get_verification_code             | 获取邮箱验证码           |
| POST    | /api/v1/register             | 注册用户           |
| POST    | /api/v1/token            | 登入  


## 完成情况

- [x] 数据库models.py
- [x] 路由api.py
- [x] 依赖项模块包含所有共享的依赖函数dependencies.py
- [x] 认证verification.py
- [x] 注册registration.py
- [x] 登入auth.py
- [x] 用户关系处理users.py
- [x] 聊天功能chat.py
- [ ] AI服务

## 使用方法

1. 启动服务器：`uvicorn api:app --reload`
2. 访问API文档：`http://localhost:8000/docs`
3. 使用API进行项目管理

# Task start
uvicorn api:app --reload