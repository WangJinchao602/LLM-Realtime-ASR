import os
import logging

class ClientConfig:
    """客户端配置"""
    
    # Flask 配置
    SECRET_KEY = 'realtime-asr-client-secret-key-2024'
    FLASK_HOST = 'localhost'
    FLASK_PORT = 5000
    
    # 本地WebSocket服务配置（用于前端连接）
    CLIENT_WS_HOST = 'localhost'
    CLIENT_WS_PORT = 8600
    
    # 服务器WebSocket配置
    SERVER_WS_HOST = '127.0.0.1'  # 服务器IP
    SERVER_WS_PORT = 8756
    
    # 音频处理配置
    SAMPLE_RATE = 16000
    BUFFER_DURATION = 2.0  # 2秒缓冲区
    CHUNK_SIZE = 1764  # 40ms at 44100Hz
    
    # 日志配置
    LOG_LEVEL = 'INFO'

# 配置日志
logging.basicConfig(
    level=getattr(logging, ClientConfig.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('client_asr.log', encoding='utf-8')
    ]
)