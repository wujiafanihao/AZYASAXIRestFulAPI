from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from models import User, SessionLocal, engine, Base
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import random
import secrets

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT密钥
SECRET_KEY = secrets.token_urlsafe(32)  # 生成一个安全的随机密钥
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 定义 OAuth2PasswordBearer 实例
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")  # 定义 oauth2_scheme

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 创建JWT令牌
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 验证密码
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# 获取当前用户
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return user

app = FastAPI()

# 内存中存储验证码及其过期时间
verification_codes = {}

# 生成并返回验证码
def generate_and_return_code(email: str):
    code = "".join(random.choices("0123456789", k=6))
    expiry_time = datetime.now(timezone.utc) + timedelta(minutes=1)
    
    # 将验证码和过期时间存储在内存中
    verification_codes[email] = {"code": code, "expiry_time": expiry_time}
    print(f"验证码已生成: {code}, 请求邮箱为：{email}")  # 打印验证码到终端
    return code

# 定义注册请求体模型
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    verification_code: str

# 注册路由
@app.post("/register")
def register_user(request: RegisterRequest, db: Session = Depends(get_db)):
    # 检查用户名是否已存在
    user = db.query(User).filter(User.username == request.username).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )
    
    # 检查邮箱是否已存在
    email_check = db.query(User).filter(User.email.ilike(request.email)).first()  # 不区分大小写查询
    if email_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已注册",
        )
    print(f"当前请求邮箱为：{request.email},验证码为：{request.verification_code}")
    # 检查用户是否已经获取过验证码
    if request.email not in verification_codes or not verification_codes[request.email]["code"]:
        return {"detail": "请先获取验证码", "flag": False}
    
    # 检查验证码是否过期
    if verification_codes[request.email]["expiry_time"] < datetime.now(timezone.utc):
        del verification_codes[request.email]  # 清理过期验证码
        return {"detail": "验证码已过期，请重新获取", "flag": False}
    
    # 检查验证码是否正确且属于该邮箱
    if request.verification_code != verification_codes[request.email]["code"]:
        return {"detail": "验证码错误或不属于该邮箱", "flag": False}
    
    # 哈希密码
    hashed_password = pwd_context.hash(request.password)
    
    # 创建新用户记录
    new_user = User(username=request.username, email=request.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 清理内存中的验证码
    del verification_codes[request.email]
    
    return {"message": "注册成功", "flag": True}

# 定义请求体模型
class EmailRequest(BaseModel):
    email: str

# 获取验证码路由
@app.post("/get_verification_code")
def get_verification_code(request: EmailRequest, db: Session = Depends(get_db)):
    # 检查邮箱是否已注册
    existing_user = db.query(User).filter(User.email.ilike(request.email)).first()  # 不区分大小写查询
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已注册",
        )
    
    # 生成验证码并返回
    code = generate_and_return_code(request.email)
    return {"message": "验证码已生成", "code": code, "Email": request.email}

# 登录请求体模型
class Token(BaseModel):
    email: str
    password: str

# 登录路由
@app.post("/token", response_model=dict)
async def login_for_access_token(
    request: Token, db: Session = Depends(get_db)
):
    # 根据邮箱查找用户
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 验证密码是否正确
    if not verify_password(request.password, user.hashed_password):
        return {"message": "false", "detail": "密码错误"}
    
    # 创建JWT令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # 返回成功信息
    return {"message": "true", "access_token": access_token, "token_type": "bearer"}

# 示例：受保护的路由
@app.get("/users/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user