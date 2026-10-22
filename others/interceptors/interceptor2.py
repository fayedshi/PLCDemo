from fastapi import FastAPI, APIRouter, Depends

app = FastAPI()

# 1. 定义拦截器
async def verify_token():
    pass # 拦截逻辑同上

# 2. 创建一个“受保护的”路由分组，并挂载 Depends 拦截器
secure_router = APIRouter(dependencies=[Depends(verify_token)])

# 3. 把所有需要保护的接口，都注册到这个 secure_router 下
@secure_router.get("/solar/data")
async def data():
    return {"msg": "受保护的数据"}

# 4. 创建一个“公开的”路由分组，不挂载任何拦截器
public_router = APIRouter()

@public_router.post("/login")
async def login():
    return {"token": "Bearer my-secret-token"} # 登录接口，不需要拦截

# 5. 最后统一注册到 app 实例中
app.include_router(public_router)
app.include_router(secure_router)
