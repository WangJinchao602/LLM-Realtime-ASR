# LLM-Realtime-ASR
借助Qwen3-Omni可以对audio进行理解的功能，对语音进行实时ASR

**具体思路**
1. 前端实时录制系统音频
2. Flask服务前端页面 → 建立WebSocket连接 → 准备就绪
3. 并将音频片段按时间切片成多个音频片段存放至缓冲区
4. 编码为WAV格式 → 调用ASR服务
5. 音频片段，调用Qwen3-Omni的ASR功能进行识别

## SimpleASR
简单实现（非实时）
1. 前端录制一段克风音频
2. 将音频转为WAV文件存放服务器或者文件系统
3. 后端调用ASR服务（Qwen3-Omni-captioner）
4. 返回识别结果

注意Qwen3-Omni-captioner 
1. 输入只能通过HTTP发送WAV格式音频文件或者Base64
2. 无法输入提示词，只能对音频进行分析，而非识别。识别模型为Qwen3-Omni需要自己部署,这里仅做测试。
3. 后续会出Qwen3-Omni如何本地部署及调用API的详细教程。

## realtime-asr-system-local
**2025-10-22更新**
增加realtime-asr-system项目

项目简介：实时铺货系统扬声器声音调用Qwen3-Omni-captioner进行实时ASR

1. 启动流程：用户访问网页 → Flask服务前端页面 → 建立WebSocket连接 → 准备就绪
2. 音频录制流程：用户点击开始录制 → 前端发送start_system_audio → WebSocket服务器接收命令 → 
启动SystemAudioService → 开始捕获系统音频 → 实时处理音频数据
3. 语音识别流程：SystemAudioService捕获音频 → 编码为WAV格式 → 调用ASR服务 → 
Qwen3模型识别语音 → 返回识别结果 → 通过WebSocket发送给前端 → 界面显示结果

**核心模块**
SystemAudioService（系统音频服务）

✅ 捕获系统扬声器音频（环回录制）

✅ 实时音频重采样（44.1kHz → 16kHz）

✅ 音频缓冲区管理（2秒缓冲区）

✅ WAV格式编码

✅ 直接调用ASR服务

✅ WebSocket通信

**2025-10-28更新**
由于Qwen3-Omni模型不支持PCM数据格式，需将PCM数据转换为完整WAV格式。

```python
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
```

**2025-11-05更新**
增加VAD（Voice Activity Detection）检测功能
使用webrtcvad将一段音频数据分类为浊音或无浊音，从而标识语音活动start和end

## realtime-asr-system-split
**2025-10-24更新**

说明：对realtime-asr-system项目进行拆分，将前端以及音频捕获后端与ASR服务端进行拆分。前端以及音频捕获后端可以部署在本地运行，ASR服务端可以部署在服务器运行。整体采用Client-Server架构。
1. 前端 --websocket--> 本地客户端WebSocket --websocket--> 服务端WebSocket

2. 服务器WebSocket → ASR服务 → 识别结果

3. 识别结果 → 服务器WebSocket → 本地客户端WebSocket → 前端
