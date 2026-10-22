from fastapi import FastAPI, Depends, Header, HTTPException, status
from typing import Optional

# 1. 编写你的拦截器函数 (切面逻辑)
async def global_auth_interceptor(authorization: Optional[str] = Header(None)):
    """
    全局路由拦截器：
    所有接口在执行前，都会自动注入并执行这个函数。
    """
    print(f"📡 [全局Depends拦截] 正在校验请求头 Token: {authorization}")
    
    # 模拟白名单：如果是在本地开发或调试，可以通过特定条件
    if authorization == "Bearer my-secret-token":
        # 验证通过，放行（可以返回用户信息，后续路由如果需要可以接收）
        return {"user": "admin", "role": "super"}
        
    # 验证失败，直接抛出 HTTPException 阻断请求，不会进入任何路由
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="🔒 鉴权失败：全局拦截器拦截，无效的 Authorization Token",
        headers={"WWW-Authenticate": "Bearer"},
    )

# 2. 【核心点】在初始化 FastAPI 时，通过 dependencies 参数注入全局拦截
app = FastAPI(
    title="光伏数据北向管理系统",
    dependencies=[Depends(global_auth_interceptor)] # 👈 挂载在这里，全站强制拦截！
)

# ==========================================
# 3. 业务路由测试 (这些路由不需要写任何多余代码，已被自动拦截)

@app.get("/api/v1/solar/power")
async def get_solar_power():
    """
    这个接口由于全局拦截器的存在，必须在 Headers 中携带:
    Authorization: Bearer my-secret-token 才能成功访问
    """
    return {"status": "online", "current_power": "450 kW"}


@app.get("/api/v1/user/profile")
async def get_user_profile():
    return {"username": "Huawei_User_01", "email": "solar@huawei.com"}
