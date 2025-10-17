# system_audio_stream_frontend.py
from flask import Flask, render_template_string, request, jsonify
import threading
import asyncio
import soundcard as sc
import numpy as np
import websockets
import struct
from time import sleep
import soxr

# 您的现有代码保持不变...
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
        print(f"Sending data chunk: {len(data)} bytes")
        return data
    else:
        return None

def encode_wav(buffer):
    pcm_data = (buffer * 0x7fff).astype(np.int16)
    wav_data = bytearray(len(buffer) * 2)
    for i in range(len(pcm_data)):
        struct.pack_into('<h', wav_data, i * 2, pcm_data[i])
    return bytes(wav_data)

SAMPLE_RATE = 44100
CHANNELS = 1
ws_url = None
streaming = False

app = Flask(__name__)

# HTML模板
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>系统音频流控制</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        .container {
            max-width: 800px;
            width: 100%;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }
        
        header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }
        
        .subtitle {
            font-size: 1.1rem;
            opacity: 0.8;
        }
        
        .control-panel {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
        }
        
        .input-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
        }
        
        input {
            width: 100%;
            padding: 12px 15px;
            border: none;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.9);
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        
        input:focus {
            outline: none;
            background: white;
            box-shadow: 0 0 0 3px rgba(74, 144, 226, 0.5);
        }
        
        .button-group {
            display: flex;
            gap: 15px;
            margin-top: 25px;
        }
        
        button {
            flex: 1;
            padding: 14px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        #startBtn {
            background: #4CAF50;
            color: white;
        }
        
        #startBtn:hover:not(:disabled) {
            background: #45a049;
            transform: translateY(-2px);
        }
        
        #stopBtn {
            background: #f44336;
            color: white;
        }
        
        #stopBtn:hover:not(:disabled) {
            background: #d32f2f;
            transform: translateY(-2px);
        }
        
        button:disabled {
            background: #cccccc;
            cursor: not-allowed;
            transform: none;
        }
        
        .status-panel {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 10px;
            padding: 20px;
        }
        
        .status-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #f44336;
        }
        
        .indicator.active {
            background: #4CAF50;
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .status-messages {
            height: 200px;
            overflow-y: auto;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            padding: 15px;
            font-family: monospace;
            font-size: 0.9rem;
        }
        
        .message {
            margin-bottom: 8px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .message.error {
            color: #ff6b6b;
        }
        
        .message.success {
            color: #4CAF50;
        }
        
        .message.info {
            color: #64b5f6;
        }
        
        footer {
            margin-top: 30px;
            text-align: center;
            font-size: 0.9rem;
            opacity: 0.7;
        }
        
        @media (max-width: 600px) {
            .container {
                padding: 20px;
            }
            
            h1 {
                font-size: 2rem;
            }
            
            .button-group {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>系统音频流控制</h1>
            <p class="subtitle">将系统音频流传输到指定的WebSocket服务器</p>
        </header>
        
        <div class="control-panel">
            <div class="input-group">
                <label for="wsUrl">WebSocket 服务器地址</label>
                <input type="text" id="wsUrl" placeholder="例如: ws://localhost:8000/asr" value="ws://localhost:8000/asr">
            </div>
            
            <div class="button-group">
                <button id="startBtn">启动音频流</button>
                <button id="stopBtn" disabled>停止音频流</button>
            </div>
        </div>
        
        <div class="status-panel">
            <div class="status-header">
                <h2>状态监控</h2>
                <div class="status-indicator">
                    <div class="indicator" id="statusIndicator"></div>
                    <span id="statusText">未连接</span>
                </div>
            </div>
            
            <div class="status-messages" id="statusMessages">
                <div class="message info">等待用户操作...</div>
            </div>
        </div>
        
        <footer>
            <p>系统音频流服务控制面板 &copy; 2023</p>
        </footer>
    </div>

    <script>
        // DOM元素
        const wsUrlInput = document.getElementById('wsUrl');
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const statusIndicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        const statusMessages = document.getElementById('statusMessages');
        
        // 添加状态消息
        function addStatusMessage(message, type = 'info') {
            const messageElement = document.createElement('div');
            messageElement.className = `message ${type}`;
            messageElement.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            statusMessages.appendChild(messageElement);
            statusMessages.scrollTop = statusMessages.scrollHeight;
        }
        
        // 更新状态指示器
        function updateStatus(isActive) {
            if (isActive) {
                statusIndicator.classList.add('active');
                statusText.textContent = '正在传输';
                startBtn.disabled = true;
                stopBtn.disabled = false;
            } else {
                statusIndicator.classList.remove('active');
                statusText.textContent = '未连接';
                startBtn.disabled = false;
                stopBtn.disabled = true;
            }
        }
        
        // 启动音频流
        async function startStreaming() {
            const wsUrl = wsUrlInput.value.trim();
            
            if (!wsUrl) {
                addStatusMessage('请输入有效的WebSocket地址', 'error');
                return;
            }
            
            try {
                addStatusMessage(`正在连接到后端服务...`, 'info');
                
                const response = await fetch('/set_ws_url', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ ws_url: wsUrl })
                });
                
                const data = await response.json();
                
                if (data.status === 'ok') {
                    addStatusMessage(data.msg, 'success');
                    updateStatus(true);
                } else if (data.status === 'running') {
                    addStatusMessage(data.msg, 'info');
                    updateStatus(true);
                } else {
                    addStatusMessage(data.msg || '启动失败', 'error');
                }
            } catch (error) {
                addStatusMessage(`连接错误: ${error.message}`, 'error');
                console.error('Error:', error);
            }
        }
        
        // 停止音频流
        async function stopStreaming() {
            try {
                addStatusMessage('正在停止音频流...', 'info');
                
                const response = await fetch('/stop_streaming', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });
                
                const data = await response.json();
                
                if (data.status === 'ok') {
                    addStatusMessage(data.msg, 'success');
                    updateStatus(false);
                } else {
                    addStatusMessage(data.msg || '停止失败', 'error');
                }
            } catch (error) {
                addStatusMessage(`停止错误: ${error.message}`, 'error');
                console.error('Error:', error);
            }
        }
        
        // 事件监听
        startBtn.addEventListener('click', startStreaming);
        stopBtn.addEventListener('click', stopStreaming);
        
        // 初始化状态
        updateStatus(false);
    </script>
</body>
</html>
'''

@app.route("/")
def index():
    """提供前端页面"""
    return render_template_string(HTML_TEMPLATE)

@app.route("/set_ws_url", methods=["POST"])
def set_ws_url():
    """
    接收 HTML 发来的 WebSocket 地址并启动推流
    """
    global ws_url, streaming
    data = request.get_json()
    ws_url = data.get("ws_url")

    if not ws_url:
        return jsonify({"status": "error", "msg": "缺少 ws_url"})

    if not streaming:
        streaming = True
        # 在新线程中启动音频流
        threading.Thread(target=start_audio_stream, daemon=True).start()
        return jsonify({"status": "ok", "msg": f"开始推流 → {ws_url}"})
    else:
        return jsonify({"status": "running", "msg": f"已在推流 → {ws_url}"})

@app.route("/stop_streaming", methods=["POST"])
def stop_streaming():
    """停止音频流"""
    global streaming
    streaming = False
    return jsonify({"status": "ok", "msg": "音频流已停止"})

def start_audio_stream():
    """在新线程中启动音频流"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_audio_stream())

async def run_audio_stream():
    """运行音频流"""
    try:
        speaker = sc.default_speaker()
        mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
        with mic.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS) as rec:
            while streaming:
                data = await asyncio.to_thread(rec.record, 1764)
                data = data.reshape(-1)

                data = soxr.resample(
                    data,
                    44100,
                    16000,
                    quality=soxr.HQ
                )
                print("data: ", data.shape)
                audio_buffer.write(data)
    except Exception as e:
        print("[推流错误]", e)

async def push_asr():
    """推送ASR数据到WebSocket"""
    async with websockets.connect(ws_url, ping_interval=None, ping_timeout=None) as websocket:
        print(f"[推流开始] 系统声音 → {ws_url}")
        while streaming:
            data = send_data_if_ready()
            if data is not None:
                await websocket.send(data)
            else:
                await asyncio.sleep(0)

async def main():
    """主协程"""
    await asyncio.gather(push_asr(), run_audio_stream())

if __name__ == "__main__":
    print("系统音频流服务已启动，访问 http://127.0.0.1:5000 使用控制面板")
    app.run(host="127.0.0.1", port=5000, debug=True)