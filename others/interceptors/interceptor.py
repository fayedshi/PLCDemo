from fastapi import APIRouter, Depends, HTTPException, Header

# 1. 定义一个拦截函数（依赖项）
async def verify_admin_token(x_token: str = Header(...)):
    """专属拦截器：只验证管理员Token"""
    if x_token != "super-secret-admin-token":
        raise HTTPException(status_code=400, detail="X-Token header invalid")
    # 可以返回用户信息给后面的路由使用
    return {"user": "admin"}

# 2. 创建 Router 时，通过 dependencies 参数绑定该拦截器
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(verify_admin_token)] # 👈 这个 Router 下的所有接口都会被拦截
)

# 3. 编写该 Router 下的接口（自动应用拦截，无需单独写）
@admin_router.get("/users")
async def read_users():
    return [{"username": "Alice"}, {"username": "Bob"}]

@admin_router.get("/settings")
async def read_settings():
    return {"theme": "dark"}
