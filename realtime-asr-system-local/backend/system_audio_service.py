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
import webrtcvad
from collections import deque
from datetime import datetime
from typing import Dict, Optional, List
from config.config import Config

logger = logging.getLogger(__name__)

class SystemAudioService:
    """系统音频服务"""
    
    def __init__(self):
        self.active_streams: Dict[str, dict] = {}  # client_id -> stream_info
        self.sample_rate = Config.SAMPLE_RATE  # 16000Hz
        self.sample_original = Config.SAMPLE_ORIGINAL  # 44100Hz
        self.frame_duration = 0.02 # 每帧 0.02s
        self.frame_size = int(self.frame_duration * self.sample_original)  # 每帧样本数
        
        # VAD 配置
        self.vad = webrtcvad.Vad(2)  # 中等敏感度 (0-3, 3最严格)
        self.vad_sample_rate = self.sample_rate  # 使用ASR采样率 16000Hz
        self.vad_frame_duration = 0.02  # 20ms帧，VAD要求10, 20 or 30ms
        self.vad_frame_size = int(self.vad_sample_rate * self.vad_frame_duration)  # 320 samples
             
        # 语音活动检测参数
        # self.speech_threshold = 0.6  # 语音检测阈值 语音能量阈值
        self.silence_threshold = 0.5  # 静音检测阈值（秒）
        self.min_speech_duration = 0.01  # 最小语音持续时间（秒）
        
    def encode_wav(self, audio_data: np.ndarray) -> bytes:
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
            'audio_queue': deque(),  # 音频数据队列
            'is_speaking': False,    # 是否在说话状态
            'speech_start_time': None,  # 语音开始时间
            'silence_start_time': None, # 静音开始时间
            'current_audio_chunk': [],  # 当前音频块
            'vad_buffer': np.array([], dtype=np.float32)  # VAD处理缓冲区
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
    
    def prepare_vad_frame(self, audio_data: np.ndarray) -> bytes:
        """准备VAD帧数据（16kHz, 16bit PCM）"""
        # 转换为16位PCM
        pcm_data = (audio_data * 0x7fff).astype(np.int16)
        return pcm_data.tobytes()
    
    def detect_speech_activity(self, stream_info: dict, audio_data: np.ndarray) -> bool:
        """检测语音活动"""
        try:
            # 添加到VAD缓冲区
            stream_info['vad_buffer'] = np.concatenate([stream_info['vad_buffer'], audio_data])
            
            # 如果缓冲区足够处理一帧VAD
            if len(stream_info['vad_buffer']) >= self.vad_frame_size:
                # 取一帧数据进行VAD检测
                frame = stream_info['vad_buffer'][:self.vad_frame_size]
                stream_info['vad_buffer'] = stream_info['vad_buffer'][self.vad_frame_size:]
                
                # 准备VAD帧
                vad_frame = self.prepare_vad_frame(frame)
                
                # 使用VAD检测语音
                is_speech = self.vad.is_speech(vad_frame, self.vad_sample_rate)
                return is_speech
                
        except Exception as e:
            logger.error(f"VAD检测错误: {e}")
            
        return False
    
    async def capture_audio(self, client_id: str):
        """为特定客户端捕获系统音频（带VAD检测）"""
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
                
                chunk_size = self.frame_size  # 20ms at 44100Hz
                
                while (client_id in self.active_streams and 
                       stream_info['is_streaming']):
                    
                    # 捕获音频数据
                    data = await asyncio.to_thread(recorder.record, chunk_size)
                    data = data.reshape(-1)
                    
                    # 重采样到16kHz（用于ASR和VAD）
                    data_resampled = soxr.resample(
                        data,
                        self.sample_original,  # 原始采样率 44100Hz
                        self.vad_sample_rate,  # 目标采样率 16000Hz
                        quality=soxr.HQ
                    )
                    
                    # 检测语音活动
                    is_speech = self.detect_speech_activity(stream_info, data_resampled)
                    current_time = datetime.now()
                    
                    if is_speech:
                        # 检测到语音
                        if not stream_info['is_speaking']:
                            # 语音开始
                            stream_info['is_speaking'] = True
                            stream_info['speech_start_time'] = current_time
                            stream_info['silence_start_time'] = None
                            logger.debug(f"客户端 {client_id} 检测到语音开始")
                        
                        # 将音频数据添加到当前块
                        stream_info['current_audio_chunk'].append(data_resampled)
                        
                    else:
                        # 没有检测到语音
                        if stream_info['is_speaking']:
                            # 在说话状态但当前帧没有语音
                            if stream_info['silence_start_time'] is None:
                                stream_info['silence_start_time'] = current_time
                            
                            # 计算静音持续时间
                            silence_duration = (current_time - stream_info['silence_start_time']).total_seconds()
                            
                            if silence_duration >= self.silence_threshold:
                                # 静音时间达到阈值，结束当前语音段
                                await self.finalize_audio_chunk(stream_info)
                            else:
                                # 仍在静音检测期内，继续收集音频
                                stream_info['current_audio_chunk'].append(data_resampled)
                        else:
                            # 不在说话状态，忽略静音帧
                            pass
                            
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
    
    async def finalize_audio_chunk(self, stream_info: dict):
        """完成当前音频块的处理"""
        if not stream_info['current_audio_chunk']:
            return
            
        # 合并所有音频数据
        combined_audio = np.concatenate(stream_info['current_audio_chunk'])
        
        # 检查音频持续时间是否满足最小要求
        audio_duration = len(combined_audio) / self.vad_sample_rate
        if audio_duration >= self.min_speech_duration:
            # 发送音频数据进行ASR处理
            await self.process_audio_with_asr(stream_info, combined_audio)
        else:
            logger.debug(f"音频段过短 ({audio_duration:.2f}s)，跳过ASR处理")
        
        # 重置状态
        stream_info['is_speaking'] = False
        stream_info['speech_start_time'] = None
        stream_info['silence_start_time'] = None
        stream_info['current_audio_chunk'] = []
        stream_info['vad_buffer'] = np.array([], dtype=np.float32)
    
    async def process_audio_with_asr(self, stream_info: dict, audio_data: np.ndarray):
        """使用ASR服务处理音频数据"""
        try:
            logger.debug(f"调用ASR服务处理音频，数据长度: {len(audio_data)} 样本，持续时间: {len(audio_data)/self.sample_rate:.2f}s")
            
            # 编码音频数据
            wav_data = self.encode_wav(audio_data)
            
            # 导入ASR服务
            from backend.asr_service import qwen_asr_service
            
            # 在线程池中调用ASR服务（避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,  # 使用默认线程池
                qwen_asr_service.recognize_speech,
                wav_data
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