import os
import base64
import logging
import time
from typing import Dict, Any
from config.config import Config

logger = logging.getLogger(__name__)

class QwenASRService:
    """Qwen3 API 的 ASR 服务"""
    
    def __init__(self):
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=Config.DASHSCOPE_API_KEY,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            self.model_name = Config.QWEN_MODEL
            self.initialized = True
            logger.info("Qwen ASR 服务初始化成功")
        except Exception as e:
            logger.error(f"Qwen ASR 服务初始化失败: {e}")
            self.initialized = False
        
    def recognize_speech(self, audio_data: bytes) -> Dict[str, Any]:
        """识别语音"""
        if not self.initialized:
            return {
                "success": False,
                "error": "ASR 服务未正确初始化"
            }
            
        try:
            start_time = time.time()
            # 编码为 base64
            base64_audio = base64.b64encode(audio_data).decode('utf-8')
            formatted_audio = f"data:audio/wav;base64,{base64_audio}"
            
            # 调用 API
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": formatted_audio,
                                },
                            }
                        ],
                    }
                ],
                timeout=30
            )
            recognized_text = completion.choices[0].message.content
            processing_time = time.time() - start_time
            
            logger.info(f"Qwen3 识别成功，耗时: {processing_time:.2f}s 「{recognized_text}」")
            
            return {
                "success": True,
                "text": recognized_text,
                "processing_time": processing_time
            }
            
        except Exception as e:
            logger.error(f"Qwen3 识别失败: {e}")
            return {
                "success": False,
                "error": f"识别失败: {str(e)}"
            }

# 全局服务实例
qwen_asr_service = QwenASRService()