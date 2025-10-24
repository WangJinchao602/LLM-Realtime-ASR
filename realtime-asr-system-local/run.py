#!/usr/bin/env python3
"""
系统声音实时识别系统启动脚本
"""

import os
import sys
import logging
import threading

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from backend.websocket_server import websocket_server
from backend.app import app

logger = logging.getLogger(__name__)

def run_websocket_server():
    """运行 WebSocket 服务器"""
    try:
        logger.info("启动 WebSocket 服务器...")
        websocket_server.run()
    except Exception as e:
        logger.error(f"WebSocket 服务器运行失败: {e}")

def run_flask_app():
    """运行 Flask 应用"""
    try:
        logger.info("启动 Flask 应用...")
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False
        )
    except Exception as e:
        logger.error(f"Flask 应用运行失败: {e}")

if __name__ == '__main__':
    logger.info("启动系统声音实时识别系统...")
    
    # 启动 WebSocket 服务器线程
    ws_thread = threading.Thread(target=run_websocket_server, daemon=True)
    ws_thread.start()
    
    logger.info("WebSocket 服务器线程已启动")
    
    # 运行 Flask 应用（主线程）
    run_flask_app()