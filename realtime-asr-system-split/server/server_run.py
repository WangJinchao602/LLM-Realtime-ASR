#!/usr/bin/env python3
"""
服务器启动脚本
"""
import logging
from backend.websocket_server import server_websocket_asr

def main():
    """主启动函数"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("正在启动语音识别服务器...")
    
    try:
        # 启动WebSocket服务器
        server_websocket_asr.run()
        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"启动服务器时发生错误: {e}")
    finally:
        logger.info("服务器已关闭")

if __name__ == '__main__':
    main()