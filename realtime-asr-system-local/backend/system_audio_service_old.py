"""
系统音频捕获服务 - 专用于捕获系统扬声器声音
"""
import asyncio
import json
import logging
import soundcard as sc
import numpy as np
import soxr
import struct
from datetime import datetime
from typing import Dict, Optional
from config.config import Config

logger = logging.getLogger(__name__)

class SystemAudioService:
    """系统音频服务"""
    
    def __init__(self):
        self.active_streams: Dict[str, dict] = {}  # client_id -> stream_info
        self.sample_rate = Config.SAMPLE_RATE
        self.buffer_duration = Config.CHUNK_DURATION  # 1秒缓冲区
        self.sample_original = Config.SAMPLE_ORIGINAL  # 44100Hz × 1s = 44100样本 修改chunk_size为1秒的原始音频数据
        self.buffer_size = int(self.buffer_duration * self.sample_rate)
        self.frame_duration = Config.FRAME_DURATION  # 每帧20ms 0.02s
        self.frame_size = int(self.frame_duration * self.sample_original)  # 每帧样本数
        
    def encode_wav(self, audio_data: np.ndarray) -> bytes:
    #     """将音频数据编码为WAV格式"""
    #     # 转换为16位PCM
    #     pcm_data = (audio_data * 0x7fff).astype(np.int16)
        
    #     # 创建WAV数据
    #     wav_data = bytearray(len(pcm_data) * 2)
        
    #     # 填充音频数据
    #     for i in range(len(pcm_data)):
    #         struct.pack_into('<h', wav_data, i * 2, pcm_data[i])
            
    #     return bytes(wav_data)
        """生成完整的WAV文件（包含文件头）"""
        pcm_data = (audio_data * 0x7fff).astype(np.int16)
        
        # WAV文件头
        riff_chunk = b'RIFF'
        file_size = len(pcm_data) * 2 + 36  # 数据大小 + 头部大小
        wave_format = b'WAVE'
        fmt_chunk = b'fmt '
        fmt_size = 16
        audio_format = 1  # PCM
        num_channels = 1   # 单声道
        sample_rate = self.sample_rate
        byte_rate = sample_rate * num_channels * 2  # 每秒字节数
        block_align = num_channels * 2
        bits_per_sample = 16
        data_chunk = b'data'
        data_size = len(pcm_data) * 2
        
        # 构建完整的WAV文件
        wav_header = struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            riff_chunk, file_size, wave_format,
            fmt_chunk, fmt_size, audio_format, num_channels,
            sample_rate, byte_rate, block_align, bits_per_sample,
            data_chunk, data_size
        )
        
        return wav_header + pcm_data.tobytes()
    
    async def start_streaming(self, websocket, client_id: str):
        """开始系统音频流"""
        if client_id in self.active_streams:
            logger.warning(f"客户端 {client_id} 的系统音频流已在运行中")
            return
            
        # 创建流信息
        stream_info = {
            'websocket': websocket,
            'client_id': client_id,
            'is_streaming': True,
            'audio_buffer': np.zeros(self.buffer_size, dtype=np.float32),
            'buffer_ptr': 0
        }
        
        self.active_streams[client_id] = stream_info
        
        try:
            logger.info(f"系统音频推流开始 → 客户端 {client_id}")
            
            # 发送开始信号
            await websocket.send(json.dumps({
                "type": "status",
                "message": "系统音频捕获已开始",
                "timestamp": datetime.now().isoformat()
            }))
            
            # 开始音频捕获
            asyncio.create_task(self.capture_audio(client_id))
            
        except Exception as e:
            logger.error(f"启动系统音频流错误: {e}")
            if client_id in self.active_streams:
                del self.active_streams[client_id]
    
    async def stop_streaming(self, client_id: str):
        """停止系统音频流"""
        if client_id in self.active_streams:
            self.active_streams[client_id]['is_streaming'] = False
            del self.active_streams[client_id]
            logger.info(f"客户端 {client_id} 的系统音频流已停止")
    
    async def capture_audio(self, client_id: str):
        """为特定客户端捕获系统音频"""
        if client_id not in self.active_streams:
            return
            
        stream_info = self.active_streams[client_id]
        websocket = stream_info['websocket']
        
        try:
            # 获取默认扬声器作为环回设备
            speaker = sc.default_speaker()
            logger.info(f"客户端 {client_id} 使用扬声器: {speaker.name}")
            
            # 创建环回录音器
            with sc.get_microphone(id=str(speaker.name), include_loopback=True).recorder(
                samplerate=self.sample_original, channels=1
            ) as recorder:
                
                chunk_size = self.frame_size # 10，20，30ms at 44100Hz 每帧
                
                while (client_id in self.active_streams and 
                       stream_info['is_streaming']):
                    
                    # 捕获音频数据
                    data = await asyncio.to_thread(recorder.record, chunk_size)
                    data = data.reshape(-1)
                    
                    # 重采样到16kHz
                    data = soxr.resample(
                        data,
                        self.sample_original,  # 原始采样率
                        self.sample_rate,  # 目标采样率
                        quality=soxr.HQ
                    )
                    
                    # 写入缓冲区
                    self.write_to_buffer(stream_info, data)
                    
                    # 检查是否需要发送数据
                    if stream_info['buffer_ptr'] >= self.buffer_size:
                        await self.send_audio_chunk(stream_info)
                        
        except Exception as e:
            logger.error(f"客户端 {client_id} 音频捕获错误: {e}")
            if client_id in self.active_streams:
                stream_info['is_streaming'] = False
                # 发送错误消息
                try:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"音频捕获错误: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }))
                except:
                    pass
    
    def write_to_buffer(self, stream_info: dict, data: np.ndarray):
        """写入数据到音频缓冲区"""
        n = len(data)
        buffer_ptr = stream_info['buffer_ptr']
        audio_buffer = stream_info['audio_buffer']
        
        if buffer_ptr + n <= self.buffer_size:
            audio_buffer[buffer_ptr:buffer_ptr + n] = data
            stream_info['buffer_ptr'] += n
        else:
            remaining = self.buffer_size - buffer_ptr
            audio_buffer[buffer_ptr:] = data[:remaining]
            stream_info['buffer_ptr'] = self.buffer_size
    
    async def send_audio_chunk(self, stream_info: dict):
        """发送音频数据块 - 直接调用ASR服务"""
        if (stream_info['buffer_ptr'] == self.buffer_size and 
            stream_info['is_streaming']):
            
            try:
                # 编码音频数据
                wav_data = self.encode_wav(stream_info['audio_buffer'])
                
                # 直接调用ASR服务处理音频
                await self.process_audio_with_asr(stream_info, wav_data)
                
                # 重置缓冲区
                stream_info['audio_buffer'] = np.zeros(self.buffer_size, dtype=np.float32)
                stream_info['buffer_ptr'] = 0
                
            except Exception as e:
                logger.error(f"处理音频数据失败: {e}")
                stream_info['is_streaming'] = False
    
    async def process_audio_with_asr(self, stream_info: dict, audio_data: bytes):
        """使用ASR服务处理音频数据"""
        try:
            logger.debug(f"调用ASR服务处理音频，数据长度: {len(audio_data)} 字节")
            
            # 导入ASR服务
            from backend.asr_service import qwen_asr_service
            
            # 在线程池中调用ASR服务（避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,  # 使用默认线程池
                qwen_asr_service.recognize_speech,
                audio_data
            )
            
            logger.debug(f"ASR服务返回结果: {result}")
            
            # 发送识别结果给前端
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
            
            await stream_info['websocket'].send(json.dumps(response))
            
        except Exception as e:
            logger.error(f"调用ASR服务失败: {e}")
            error_response = {
                "type": "error",
                "message": f"ASR服务调用失败: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            await stream_info['websocket'].send(json.dumps(error_response))

# 全局系统音频服务实例
system_audio_service = SystemAudioService()