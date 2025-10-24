"""
客户端音频服务 - 捕获系统音频并转发到服务器
"""
import asyncio
import json
import logging
import websockets
import soundcard as sc
import numpy as np
import soxr
import struct
from datetime import datetime
from typing import Dict, Optional
from config.config import ClientConfig

logger = logging.getLogger(__name__)

class ClientAudioService:
    """客户端音频服务"""
    
    def __init__(self):
        self.active_streams: Dict[str, dict] = {}
        self.server_websocket = None
        self.sample_rate = ClientConfig.SAMPLE_RATE
        self.buffer_duration = ClientConfig.BUFFER_DURATION
        self.buffer_size = int(self.buffer_duration * self.sample_rate)
        self.is_connected_to_server = False
        
    async def connect_to_server(self):
        """连接到服务器WebSocket"""
        try:
            server_url = f"ws://{ClientConfig.SERVER_WS_HOST}:{ClientConfig.SERVER_WS_PORT}"
            self.server_websocket = await websockets.connect(server_url)
            self.is_connected_to_server = True
            logger.info(f"已连接到服务器: {server_url}")
            
            # 启动消息接收循环
            asyncio.create_task(self.receive_server_messages())
            
        except Exception as e:
            logger.error(f"连接服务器失败: {e}")
            self.is_connected_to_server = False
            
    async def receive_server_messages(self):
        """接收服务器消息并转发给前端"""
        try:
            async for message in self.server_websocket:
                # 将服务器消息转发给所有前端客户端
                for client_id, stream_info in self.active_streams.items():
                    try:
                        await stream_info['websocket'].send(message)
                    except Exception as e:
                        logger.error(f"转发消息到客户端 {client_id} 失败: {e}")
        except Exception as e:
            logger.error(f"接收服务器消息失败: {e}")
            self.is_connected_to_server = False
            
    def encode_wav(self, audio_data: np.ndarray) -> bytes:
        """将音频数据编码为WAV格式"""
        pcm_data = (audio_data * 0x7fff).astype(np.int16)
        wav_data = bytearray(len(pcm_data) * 2)
        
        for i in range(len(pcm_data)):
            struct.pack_into('<h', wav_data, i * 2, pcm_data[i])
            
        return bytes(wav_data)
    
    async def start_streaming(self, websocket, client_id: str):
        """开始系统音频流"""
        if client_id in self.active_streams:
            logger.warning(f"客户端 {client_id} 的系统音频流已在运行中")
            return
            
        # 确保连接到服务器
        if not self.is_connected_to_server:
            await self.connect_to_server()
            if not self.is_connected_to_server:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "无法连接到服务器",
                    "timestamp": datetime.now().isoformat()
                }))
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
            logger.info(f"客户端 {client_id} 系统音频推流开始")
            
            # 发送开始信号到前端
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
                samplerate=44100, channels=1
            ) as recorder:
                
                chunk_size = ClientConfig.CHUNK_SIZE
                
                while (client_id in self.active_streams and 
                       stream_info['is_streaming'] and
                       self.is_connected_to_server):
                    
                    # 捕获音频数据
                    data = await asyncio.to_thread(recorder.record, chunk_size)
                    data = data.reshape(-1)
                    
                    # 重采样到16kHz
                    data = soxr.resample(
                        data,
                        44100,
                        16000,
                        quality=soxr.HQ
                    )
                    
                    # 写入缓冲区
                    self.write_to_buffer(stream_info, data)
                    
                    # 检查是否需要发送数据到服务器
                    if stream_info['buffer_ptr'] >= self.buffer_size:
                        await self.send_audio_to_server(stream_info)
                        
        except Exception as e:
            logger.error(f"客户端 {client_id} 音频捕获错误: {e}")
            if client_id in self.active_streams:
                stream_info['is_streaming'] = False
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
    
    async def send_audio_to_server(self, stream_info: dict):
        """发送音频数据到服务器"""
        if (stream_info['buffer_ptr'] == self.buffer_size and 
            stream_info['is_streaming'] and
            self.is_connected_to_server):
            
            try:
                # 编码音频数据
                wav_data = self.encode_wav(stream_info['audio_buffer'])
                
                # 发送到服务器
                await self.server_websocket.send(wav_data)
                
                logger.debug(f"发送音频数据到服务器，长度: {len(wav_data)} 字节")
                
                # 重置缓冲区
                stream_info['audio_buffer'] = np.zeros(self.buffer_size, dtype=np.float32)
                stream_info['buffer_ptr'] = 0
                
            except Exception as e:
                logger.error(f"发送音频数据到服务器失败: {e}")
                self.is_connected_to_server = False
    
    async def handle_client_message(self, websocket, client_id: str, message):
        """处理客户端消息"""
        try:
            if isinstance(message, str):
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "start_system_audio":
                    await self.start_streaming(websocket, client_id)
                elif message_type == "stop_system_audio":
                    await self.stop_streaming(client_id)
                    
        except Exception as e:
            logger.error(f"处理客户端消息失败: {e}")

# 全局客户端音频服务实例
client_audio_service = ClientAudioService()