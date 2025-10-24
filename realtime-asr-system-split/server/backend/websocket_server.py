import asyncio
import websockets
import json
import logging
import time
from datetime import datetime
from typing import Dict, Set
from concurrent.futures import ThreadPoolExecutor

from config.config import Config as ServerConfig
from backend.asr_service import qwen_asr_service

logger = logging.getLogger(__name__)

class ServerWebSocketASR:
    """服务器WebSocket ASR服务 - 接收音频并返回识别结果"""
    
    def __init__(self):
        self.host = ServerConfig.WS_HOST
        self.port = ServerConfig.WS_PORT
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        
    async def handle_client(self, websocket):
        """处理客户端连接"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.connected_clients.add(websocket)
        
        logger.info(f"客户端连接: {client_id}, 当前连接数: {len(self.connected_clients)}")
        
        try:
            # 发送连接成功消息
            await websocket.send(json.dumps({
                "type": "status",
                "message": "已连接到ASR服务器",
                "timestamp": datetime.now().isoformat()
            }))
            
            # 处理消息循环
            async for message in websocket:
                await self.handle_audio_message(websocket, client_id, message)
                
        except websockets.ConnectionClosed:
            logger.info(f"客户端断开连接: {client_id}")
        except Exception as e:
            logger.error(f"处理客户端 {client_id} 时出错: {e}")
        finally:
            if websocket in self.connected_clients:
                self.connected_clients.remove(websocket)
            logger.info(f"客户端清理完成: {client_id}, 剩余连接数: {len(self.connected_clients)}")
    
    async def handle_audio_message(self, websocket, client_id: str, message):
        """处理音频消息"""
        try:
            if isinstance(message, bytes):
                # 二进制消息是音频数据
                logger.debug(f"收到音频数据，长度: {len(message)} 字节")
                await self.process_audio_data(websocket, client_id, message)
            else:
                # 文本消息可能是控制命令
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "ping":
                    await websocket.send(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }))
                else:
                    logger.warning(f"未知消息类型: {message_type}")
                    
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"处理消息时出错: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }))
    
    async def process_audio_data(self, websocket, client_id: str, audio_data: bytes):
        """处理音频数据并返回识别结果"""
        try:
            logger.debug(f"处理客户端 {client_id} 的音频数据")
            
            # 在线程池中调用ASR服务
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.thread_pool,
                qwen_asr_service.recognize_speech,
                audio_data
            )
            
            logger.debug(f"ASR服务返回结果: {result}")
            
            # 发送识别结果给客户端
            if result.get("success", False):
                response = {
                    "type": "transcript",
                    "text": result["text"],
                    "timestamp": datetime.now().isoformat(),
                    "processing_time": result.get("processing_time", 0)
                }
                logger.info(f"ASR识别成功: 「{result['text']}」, 耗时: {result.get('processing_time', 0):.2f}s")
            else:
                response = {
                    "type": "error",
                    "message": result.get("error", "识别失败"),
                    "timestamp": datetime.now().isoformat()
                }
                logger.warning(f"ASR识别失败: {result.get('error')}")
            
            await websocket.send(json.dumps(response))
            
        except Exception as e:
            logger.error(f"处理音频数据失败: {e}")
            error_response = {
                "type": "error",
                "message": f"处理音频数据失败: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(error_response))
    
    async def start_server(self):
        """启动 WebSocket 服务器"""
        logger.info(f"启动服务器 WebSocket ASR 服务在 {self.host}:{self.port}")
        
        async with websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10,
            max_size=ServerConfig.MAX_AUDIO_SIZE
        ):
            logger.info("服务器 WebSocket ASR 服务已启动，等待客户端连接...")
            await asyncio.Future()  # 永久运行
    
    def run(self):
        """运行服务器"""
        asyncio.run(self.start_server())

# 全局服务器实例
server_websocket_asr = ServerWebSocketASR()