#!/usr/bin/env python3
"""
客户端启动脚本
启动本地WebSocket服务（8600端口）和Flask应用（5000端口）
"""
import asyncio
import threading
import logging
from backend.client_audio_service import client_audio_service
from config.config import ClientConfig
import websockets
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class ClientWebSocketServer:
    """客户端WebSocket服务器 - 处理前端连接"""
    
    def __init__(self):
        self.host = ClientConfig.CLIENT_WS_HOST
        self.port = ClientConfig.CLIENT_WS_PORT
        self.connected_clients = {}
        
    async def handle_client(self, websocket):
        """处理客户端连接"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.connected_clients[client_id] = websocket
        
        logger.info(f"前端客户端连接: {client_id}")
        
        try:
            # 发送连接成功消息
            await websocket.send(json.dumps({
                "type": "status",
                "message": "已连接到本地音频服务",
                "timestamp": datetime.now().isoformat()
            }))
            
            # 处理消息循环
            async for message in websocket:
                await client_audio_service.handle_client_message(websocket, client_id, message)
                
        except websockets.ConnectionClosed:
            logger.info(f"前端客户端断开连接: {client_id}")
        except Exception as e:
            logger.error(f"处理前端客户端 {client_id} 时出错: {e}")
        finally:
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
            # 停止该客户端的音频流
            await client_audio_service.stop_streaming(client_id)
    
    async def start_server(self):
        """启动 WebSocket 服务器"""
        logger.info(f"启动客户端 WebSocket 服务器在 {self.host}:{self.port}")
        
        async with websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10
        ):
            logger.info("客户端 WebSocket 服务器已启动，等待前端连接...")
            await asyncio.Future()  # 永久运行

def run_flask_app():
    """运行Flask应用"""
    from backend.app import app
    from config.config import ClientConfig
    
    app.run(
        host=ClientConfig.FLASK_HOST,
        port=ClientConfig.FLASK_PORT,
        debug=False,  # 在生产环境中设为False
        use_reloader=False
    )

def run_websocket_server():
    """运行本地WebSocket服务器"""
    server = ClientWebSocketServer()
    asyncio.run(server.start_server())

if __name__ == '__main__':
    logger.info("启动客户端服务...")
    
    # 在单独的线程中运行Flask应用
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    logger.info(f"Flask 应用已启动: http://localhost:5000")
    
    # 在主线程中运行WebSocket服务器
    run_websocket_server()