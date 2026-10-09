import cv2
import time

def connect_hikvision_rtsp():
    # 1. 配置海康摄像头的参数（根据你的实际情况修改）
    USER = "admin"
    PASSWORD = "LC1314pp"           # 你的摄像头密码
    IP = "192.168.0.241"            # 你的摄像头IP
    PORT = "554"
    
    # 2. 拼接完整的 RTSP URL (这里采用 H.264 主码流)
    # rtsp_url = f"rtsp://{USER}:{PASSWORD}@{IP}:{PORT}/h264/ch1/main/av_stream"
    # rtsp_url = f"rtsp://{IP}:{PORT}/h264/ch1/main/av_stream"
    rtsp_url = f"rtsp://{USER}:{PASSWORD}@{IP}:{PORT}/Streaming/Channels/101"
    print(f"正在连接海康威视 RTSP 流: {rtsp_url}")

    # 3. 创建视频捕获对象
    cap = cv2.VideoCapture(rtsp_url)

    # 优化参数：减少网络流延迟 (部分 OpenCV 版本有效)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print("❌ 无法连接到摄像头，请检查：\n1. IP、账号、密码是否正确\n2. 电脑与摄像头是否在同一局域网\n3. 摄像头是否开启了RTSP服务")
        return

    print("✅ 成功连接到海康摄像头！按下 'Q' 键退出播放。")

    # 4. 循环读取视频帧并显示
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("⚠️ 丢帧或视频流中断，正在尝试重新读取...")
            time.sleep(1)
            continue

        # 调整窗口大小展示（可选，防止大码流分辨率过大撑满屏幕）
        show_frame = cv2.resize(frame, (800, 450))

        # 显示画面
        cv2.imshow("Hikvision Monitor Demo", show_frame)

        # 监听键盘，按下 Q 键退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 5. 释放资源
    cap.release()
    cv2.destroyAllWindows()
    print("👋 已断开连接并关闭窗口。")

if __name__ == "__main__":
    connect_hikvision_rtsp()
