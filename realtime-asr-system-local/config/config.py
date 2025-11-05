# import os
# from dotenv import load_dotenv

# load_dotenv()

# class Config:
#     """应用配置"""
#     # Flask 配置
#     SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    
#     # WebSocket 配置
#     WS_HOST = os.getenv('WS_HOST', 'localhost')
#     WS_PORT = int(os.getenv('WS_PORT', 8765))
    
#     # ASR 服务配置
#     ASR_SERVICE_URL = os.getenv('ASR_SERVICE_URL', 'http://localhost:8000')
    
#     # Qwen3 API 配置
#     DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
#     QWEN_MODEL = os.getenv('QWEN_MODEL', 'qwen3-omni-30b-a3b-captioner')
    
#     # 音频处理配置
#     MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB
#     SAMPLE_RATE = 16000
#     CHUNK_DURATION = 2.0  # 每2秒处理一次
    
#     # 日志配置
#     LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

import os
import logging

class Config:
    """应用配置 - 硬编码版本"""
    
    # Flask 配置
    SECRET_KEY = 'realtime-asr-system-secret-key-2024'
    
    # WebSocket 配置
    WS_HOST = 'localhost'
    WS_PORT = 8765

    
    # Qwen3 API 配置 - 请替换为您的实际 API Key
    DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
    QWEN_MODEL = 'qwen3-omni-30b-a3b-captioner'
    
    # 音频处理配置
    MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB
    SAMPLE_ORIGINAL = 44100 # 44.1kHz
    SAMPLE_RATE = 16000 # 16kHz
    CHUNK_DURATION = 2.0  # 每2秒处理一次
    
    # 日志配置
    LOG_LEVEL = 'INFO'

# 配置日志
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('realtime_asr.log', encoding='utf-8')
    ]
)