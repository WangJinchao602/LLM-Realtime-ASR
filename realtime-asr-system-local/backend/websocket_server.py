import asyncio
import websockets
import json
import logging
import time
from datetime import datetime
from typing import Dict, Set
from concurrent.futures import ThreadPoolExecutor

from config.config import Config
from backend.asr_service import qwen_asr_service
from backend.system_audio_service import system_audio_service

logger = logging.getLogger(__name__)

class WebSocketASRServer:
    """WebSocket ASR 服务器 - 专用于系统音频识别"""
    
    def __init__(self):
        self.host = Config.WS_HOST
        self.port = Config.WS_PORT
        self.connected_clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.system_audio_clients: Set[str] = set()
        self.thread_pool = ThreadPoolExecutor(max_workers=5)
        self.main_loop = None
        
    async def handle_client(self, websocket):
        """处理客户端连接"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.connected_clients[client_id] = websocket
        
        logger.info(f"客户端连接: {client_id}, 当前连接数: {len(self.connected_clients)}")
        
        try:
            # 发送连接成功消息
            await websocket.send(json.dumps({
                "type": "status",
                "message": "已连接到系统音频识别服务",
                "timestamp": datetime.now().isoformat()
            }))
            
            # 处理消息循环
            async for message in websocket:
                await self.handle_message(websocket, client_id, message)
                
        except websockets.ConnectionClosed:
            logger.info(f"客户端断开连接: {client_id}")
        except Exception as e:
            logger.error(f"处理客户端 {client_id} 时出错: {e}")
        finally:
            # 清理资源
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
            if client_id in self.system_audio_clients:
                self.system_audio_clients.remove(client_id)
            logger.info(f"客户端清理完成: {client_id}, 剩余连接数: {len(self.connected_clients)}")
    
    async def handle_message(self, websocket, client_id: str, message):
        """处理接收到的消息"""
        try:
            logger.debug(f"收到来自 {client_id} 的消息，类型: {type(message)}")
            
            # 如果是二进制消息，记录但不处理（现在由系统音频服务直接处理）
            if isinstance(message, bytes):
                logger.debug(f"收到二进制消息，长度: {len(message)} 字节 - 系统音频服务已直接处理ASR")
                return
                
            # 如果是文本消息，解析为JSON
            elif isinstance(message, str):
                logger.debug(f"收到文本消息: {message[:100]}...")
                
                # 检查消息是否为空
                if not message.strip():
                    logger.warning(f"收到空消息来自 {client_id}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "收到空消息"
                    }))
                    return
                    
                data = json.loads(message)
                message_type = data.get("type")
                
                logger.debug(f"解析消息类型: {message_type}")
                
                if message_type == "start_system_audio":
                    await self.handle_start_system_audio(websocket, client_id, data)
                elif message_type == "stop_system_audio":
                    await self.handle_stop_system_audio(websocket, client_id)
                elif message_type == "ping":
                    await self.handle_ping(websocket, client_id)
                else:
                    logger.warning(f"未知消息类型: {message_type}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"未知的消息类型: {message_type}"
                    }))
                    
        except json.JSONDecodeError as e:
            logger.error(f"客户端 {client_id} 发送了无效的JSON数据: {e}")
            logger.error(f"无效消息内容: {message}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"无效的JSON格式: {str(e)}"
            }))
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"处理消息时出错: {str(e)}"
            }))
    
    async def handle_start_system_audio(self, websocket, client_id: str, data: dict):
        """处理开始系统音频录制信号"""
        try:
            # 记录这个客户端正在使用系统音频
            self.system_audio_clients.add(client_id)
            
            # 启动系统音频服务，并传入当前WebSocket连接
            await system_audio_service.start_streaming(websocket, client_id)
            
            logger.info(f"客户端 {client_id} 开始系统音频录制")
            await websocket.send(json.dumps({
                "type": "status",
                "message": "系统音频录制已开始",
                "timestamp": datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"启动系统音频录制失败: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"启动系统音频录制失败: {str(e)}"
            }))
    
    async def handle_stop_system_audio(self, websocket, client_id: str):
        """处理停止系统音频录制信号"""
        try:
            # 从系统音频客户端集合中移除
            if client_id in self.system_audio_clients:
                self.system_audio_clients.remove(client_id)
            
            # 停止系统音频服务
            await system_audio_service.stop_streaming(client_id)
            
            logger.info(f"客户端 {client_id} 停止系统音频录制")
            await websocket.send(json.dumps({
                "type": "status",
                "message": "系统音频录制已停止",
                "timestamp": datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"停止系统音频录制失败: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"停止系统音频录制失败: {str(e)}"
            }))
    
    async def handle_ping(self, websocket, client_id: str):
        """处理心跳检测"""
        await websocket.send(json.dumps({
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        }))
    
    async def start_server(self):
        """启动 WebSocket 服务器"""
        # 在服务器启动时获取并保存主线程的事件循环
        self.main_loop = asyncio.get_event_loop()
        
        logger.info(f"启动 WebSocket ASR 服务器在 {self.host}:{self.port}")
        
        async with websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10,
            max_size=Config.MAX_AUDIO_SIZE
        ):
            logger.info("WebSocket ASR 服务器已启动，等待连接...")
            await asyncio.Future()  # 永久运行
    
    def run(self):
        """运行服务器"""
        asyncio.run(self.start_server())

# 全局服务器实例
websocket_server = WebSocketASRServer()