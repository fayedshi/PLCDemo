from flask import Flask, request, jsonify
from functools import wraps

app = Flask(__name__)

# 1. 编写自定义拦截器装饰器
def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 拦截逻辑：从请求头拿到角色并校验
            user_role = request.headers.get("X-User-Role")
            if user_role != required_role:
                return jsonify({"error": f"需要 {required_role} 权限才能访问"}), 403
            # 校验通过，放行进入核心路由函数
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 2. 在特定的路由上按需精准挂载
@app.route("/dashboard")
@role_required("vip") # 👈 只拦截和保护这一个接口
def dashboard():
    return jsonify({"data": "欢迎 VIP 用户"})

@app.route("/public-info")
def public_info(): # 👈 这个接口完全不被拦截
    return jsonify({"data": "公开信息"})
