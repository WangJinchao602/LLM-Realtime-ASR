import os
import logging

class Config:
    """服务器配置"""
    
    # 服务端 WebSocket 配置
    WS_HOST = '0.0.0.0'  # 监听所有接口
    WS_PORT = 8756
    
    # Qwen3 API 配置
    Qwen3_API_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
    DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
    QWEN_MODEL = 'qwen3-omni-30b-a3b-captioner'
    
    # 音频处理配置
    MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB
    
    # 日志配置
    LOG_LEVEL = 'INFO'

# 配置日志
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('server_asr.log', encoding='utf-8')
    ]
)