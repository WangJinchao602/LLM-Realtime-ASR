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


**2025-10-22更新：realtime-asr-system**
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





