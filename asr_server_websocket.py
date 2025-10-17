# asr_server.py
import asyncio
import websockets
import json
import numpy as np
import wave
import io
from datetime import datetime
import threading
from queue import Queue

class SpeechRecognizer:
    """模拟语音识别器（实际项目中可替换为真实ASR引擎）"""
    
    def __init__(self):
        self.audio_buffer = b""
        self.sample_rate = 16000
        self.chunk_size = 640  # 40ms at 16kHz
        
    def process_audio_chunk(self, audio_data):
        """
        处理音频数据块并返回识别结果
        实际应用中这里会调用真实的ASR引擎
        """
        # 模拟处理延迟
        # time.sleep(0.1)
        
        # 这里可以添加真实的语音识别代码，例如：
        # - 使用 Whisper
        # - 使用 Google Speech-to-Text
        # - 使用 Azure Cognitive Services
        # - 使用 阿里云/腾讯云 语音识别
        
        # 模拟识别结果
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # 简单模拟：根据音频能量生成伪文本
        if len(audio_data) > 0:
            # 转换为numpy数组
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            energy = np.sqrt(np.mean(audio_array**2))
            
            if energy > 1000:  # 有声音
                return {
                    "text": f"识别文本示例 [{current_time}]",
                    "confidence": 0.85,
                    "is_final": False,
                    "energy": float(energy)
                }
            else:  # 静音
                return {
                    "text": "",
                    "confidence": 0.0,
                    "is_final": False,
                    "energy": float(energy)
                }
        
        return {
            "text": "",
            "confidence": 0.0,
            "is_final": False,
            "energy": 0.0
        }

class ASRServer:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.recognizer = SpeechRecognizer()
        self.connected_clients = set()
        
    async def handle_audio_stream(self, websocket, path):
        """处理音频流 WebSocket 连接"""
        client_id = id(websocket)
        print(f"客户端连接: {client_id}")
        self.connected_clients.add(websocket)
        
        try:
            async for audio_data in websocket:
                # 处理接收到的音频数据
                if isinstance(audio_data, bytes):
                    # 调用语音识别器处理音频
                    result = self.recognizer.process_audio_chunk(audio_data)
                    
                    # 发送识别结果回客户端
                    response = {
                        "type": "recognition_result",
                        "data": result,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    await websocket.send(json.dumps(response))
                    
                    # 打印识别信息（可选）
                    if result["text"]:
                        print(f"识别结果: {result['text']} (置信度: {result['confidence']:.2f})")
                        
        except websockets.exceptions.ConnectionClosed:
            print(f"客户端断开: {client_id}")
        finally:
            self.connected_clients.remove(websocket)
    
    async def start_server(self):
        """启动 WebSocket 服务器"""
        print(f"语音识别服务启动在: ws://{self.host}:{self.port}")
        print("等待音频流连接...")
        
        async with websockets.serve(
            self.handle_audio_stream, 
            self.host, 
            self.port,
            ping_interval=20,
            ping_timeout=10
        ):
            await asyncio.Future()  # 永久运行
    
    def run(self):
        """运行服务器"""
        asyncio.run(self.start_server())

if __name__ == "__main__":
    server = ASRServer()
    server.run()