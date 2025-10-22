import asyncio
import websockets
import json
import base64
import io
import wave
import requests
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Qwen3 ASR模型API地址
QWEN3_API_URL = "http://localhost:8000/recognize"  # 假设Qwen3模型运行在这个地址

# WebSocket服务器处理函数
async def handle_client(websocket, path):
    logger.info(f"客户端连接: {websocket.remote_address}")
    try:
        # 向前端发送连接成功消息
        await websocket.send(json.dumps({
            "type": "status",
            "message": "已连接到ASR服务"
        }))
        
        # 持续接收前端发送的音频数据
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data["type"] == "audio":
                    # 获取base64编码的音频数据
                    base64_audio = data["data"]
                    
                    # 处理音频数据并发送给ASR模型
                    recognized_text = await recognize_speech(base64_audio)
                    
                    # 将识别结果发送回前端
                    await websocket.send(json.dumps({
                        "type": "transcript",
                        "text": recognized_text
                    }))
                
            except Exception as e:
                logger.error(f"处理消息时出错: {e}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": str(e)
                }))
    except websockets.ConnectionClosed as e:
        logger.info(f"客户端断开连接: {websocket.remote_address}, 原因: {e}")
    except Exception as e:
        logger.error(f"客户端处理异常: {e}")

# 调用Qwen3 ASR模型进行语音识别
async def recognize_speech(base64_audio):
    try:
        # 由于Qwen3模型需要base64格式的音频，这里可以直接发送
        # 如果需要进行额外处理，可以在这里添加
        
        # 调用Qwen3 API
        response = requests.post(
            QWEN3_API_URL,
            json={"audio_data": base64_audio},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("text", "无法识别")
        else:
            logger.error(f"Qwen3 API调用失败: {response.status_code}, {response.text}")
            return f"识别服务错误: {response.status_code}"
    except Exception as e:
        logger.error(f"语音识别过程中出错: {e}")
        return f"识别过程错误: {str(e)}"

# 启动WebSocket服务器
async def main():
    async with websockets.serve(handle_client, "localhost", 8765):
        logger.info("ASR WebSocket服务器已启动，监听端口 8765")
        await asyncio.Future()  # 保持服务器运行

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务器已停止")