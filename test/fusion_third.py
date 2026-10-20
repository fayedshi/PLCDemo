import requests

# 1. 基础配置信息
BASE_URL = "https://cn.fusionsolar.huawei.com/thirdData"
USERNAME = "north_api_user"
PASSWORD = "north@123"

session = requests.Session()
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}
# 2. 登录获取 Token
# ⚠️ 华为限制：10分钟内最多登录5次，切勿在循环或高频请求中重复执行此登录步骤
response = session.post(
    f"{BASE_URL}/login", 
    json={"userName": USERNAME, "systemCode": PASSWORD},
    headers = headers
)

# 打印 HTTP 状态码（应该为 200）
print(f"HTTP状态码: {response.status_code}")
try:
    # print(f"reponse: {response.text[:500]}")
    res_json = response.json()
    print(f"服务器返回内容: {res_json}，fail code{res_json['failCode']}")

# if res_json.get("success") is True:
#     token = response.headers.get("xsrf-token")
#     print(f"🎉 登录成功！获取到的 Token 为: {token}")
# else:
#     fail_code = res_json.get("failCode")
#     message = res_json.get("message")
#     print(f"❌ 登录失败！华为返回的错误码(failCode): {fail_code}，提示信息: {message}")
#     # exit(0)
# token = response.headers.get("xsrf-token")

except Exception:
    print(f"登录失败，响应内容: {response.text[:500]}")

print("登录成功，正在获取新版电站列表...")

# 3. 请求新版带分页功能的 /thirdData/stations 接口
# ⚠️ 新接口为 POST 方法，必须在 Body 中传入 pageNo 参数
token = response.headers.get("xsrf-token")
stations_resp = session.post(
    f"{BASE_URL}/stations",
    headers={"xsrf-token": token, "Content-Type": "application/json"},
    json={"pageNo": 1} # 最小请求体，查询第1页数据 ,"gridConnectedStartTime":1701561600000
)

# 4. 打印返回的电站数据结果
print(stations_resp.json())
