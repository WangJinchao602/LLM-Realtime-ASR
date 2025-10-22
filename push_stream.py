# system_audio_stream.py
from flask import Flask, request, make_response
from flask_cors import CORS
import threading
import asyncio
import soundcard as sc
import numpy as np
import websockets
import struct
from time import sleep
import soxr

class Buffer:
    def __init__(self, size, dtype=np.float32):
        self.buffer = np.zeros(size, dtype=dtype)
        self.size = size   #容量
        self.write_ptr = 0
        self.read_ptr = 0
        self.available = 0  #当前可读样本数
        self.dtype = dtype

    def write(self, data: np.ndarray):
        n = len(data)
        if n > self.size:
            data = data[-self.size:]  # 只保留最新
            n = self.size
        end = (self.write_ptr + n) % self.size
        if self.write_ptr < end:
            self.buffer[self.write_ptr:end] = data
        else:
            part = self.size - self.write_ptr
            self.buffer[self.write_ptr:] = data[:part]
            self.buffer[:end] = data[part:]
        self.write_ptr = end
        self.available = min(self.available + n, self.size)

    def read(self, n):
        if n > self.available:
            return None  # 数据不足
        end = (self.read_ptr + n) % self.size
        if self.read_ptr < end:
            out = self.buffer[self.read_ptr:end].copy()
        else:
            part = self.size - self.read_ptr
            out = np.concatenate([
                self.buffer[self.read_ptr:],
                self.buffer[:end]
            ])
        self.read_ptr = end
        self.available -= n
        return out
audio_buffer = Buffer(10240)

def low_pass_filter(input_data, target_sample_rate = 16000,sample_rate = 44100):
    cutoff = target_sample_rate / 2
    rc = 1 / (2 * np.pi * cutoff)
    dt = 1 / sample_rate
    alpha = dt / (rc + dt)

    filtered = np.zeros_like(input_data, dtype=np.float32)
    filtered[0] = input_data[0]

    for i in range(1, len(input_data)):
        filtered[i] = alpha * input_data[i] + (1 - alpha) * filtered[i - 1]
    return filtered

def resample_audio(input_data, target_sample_rate = 16000,sample_rate = 44100):
    ratio = sample_rate / target_sample_rate
    new_length = int(round(len(input_data) / ratio))
    output = np.zeros(new_length, dtype=np.float32)

    for i in range(new_length):
        index = i * ratio
        left = int(np.floor(index))
        right = int(np.ceil(index))
        fraction = index - left

        if right >= len(input_data):
            output[i] = input_data[left]
        else:
            output[i] = input_data[left] * (1 - fraction) + input_data[right] * fraction

    return output

def send_data_if_ready():
    if audio_buffer.available >= 640:
        send_buffer = audio_buffer.read(640)
        data = encode_wav(send_buffer)

        # 模拟postMessage发送
        print(f"Sending data chunk: {len(data)} bytes")
        return data
    else:
        return None

def encode_wav(buffer):
    # # 转换为16位PCM
    pcm_data = (buffer * 0x7fff).astype(np.int16)

    # 创建WAV数据
    wav_data = bytearray(len(buffer) * 2)

    # 仅填充音频数据
    for i in range(len(pcm_data)):
        struct.pack_into('<h', wav_data, i * 2, pcm_data[i])

    return bytes(wav_data)



SAMPLE_RATE = 44100
CHANNELS = 1
ws_url = None
streaming = False


app = Flask(__name__)
CORS(app)
@app.route("/set_ws_url", methods=["POST"])
def set_ws_url():
    """
    接收 HTML 发来的 WebSocket 地址并启动推流
    """
    global ws_url, streaming
    data = request.get_json()
    ws_url = data.get("ws_url")

    if not ws_url:
        resp = make_response({"status": "error", "msg": "缺少 ws_url"})
        resp.headers["Access-Control-Allow-Origin"] = "*"  # ★ 允许跨域
        return resp

    if not streaming:
        streaming = True
        # threading.Thread(target=push_asr, daemon=False).start()
        # threading.Thread(target=stream_audio, daemon=False).start()
        asyncio.run(main())
        resp = make_response({"status": "ok", "msg": f"开始推流 → {ws_url}"})
    else:
        resp = make_response({"status": "running", "msg": f"已在推流 → {ws_url}"})

    resp.headers["Access-Control-Allow-Origin"] = "*"  # ★ 允许跨域
    return resp


async def main():
    await asyncio.gather(push_asr(), stream_audio())





async def stream_audio():
    try:
        speaker = sc.default_speaker()
        mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
        with mic.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS) as rec:
            while True:
                data = await asyncio.to_thread(rec.record, 1764)
                data = data.reshape(-1)

                data = soxr.resample(
                    data,  # 输入音频数据（numpy数组）
                    44100,  # 原始采样率（如96000）
                    16000,  # 目标采样率（如44100）
                    quality=soxr.HQ  # 质量预设：HQ（高）、MQ（中）、LQ（低）
                )
                print("data: ", data.shape)
                # data = low_pass_filter(data)
                # data = resample_audio(data)
                audio_buffer.write(data)
    except Exception as e:
        print("[推流错误]", e)


async def push_asr():
    async with websockets.connect(ws_url, ping_interval=None, ping_timeout=None) as websocket:
        print(f"[推流开始] 系统声音 → {ws_url}")
        while True:
            data = send_data_if_ready()
            if data is not None:
                await websocket.send(data)
            else:
                await asyncio.sleep(0)




if __name__ == "__main__":
    print("Python 已启动，等待 HTML 推送 ws_url ...")
    app.run(host="127.0.0.1", port=5000)