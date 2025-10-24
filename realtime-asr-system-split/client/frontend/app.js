class SystemAudioASR {
    constructor() {
        this.websocket = null;
        this.isConnected = false;
        this.isRecording = false;
        this.recordingTime = 0;
        this.timerInterval = null;
        this.resultCount = 0;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.wasRecordingBeforeUnload = false; // 新增：记录页面卸载前的录制状态

        this.wsHost = window.location.hostname;
        this.wsPort = '8600';
        
        this.initializeElements();
        this.attachEventListeners();
        this.initializeWebSocket();
    }
    
    initializeElements() {
        // 控制按钮
        this.startBtn = document.getElementById('startRecord');
        this.stopBtn = document.getElementById('stopRecord');
        this.clearBtn = document.getElementById('clearText');
        
        // 状态显示
        this.statusIndicator = document.getElementById('statusIndicator');
        this.statusText = document.getElementById('statusText');
        this.connectionStatus = document.getElementById('connectionStatus');
        this.recordingTimer = document.getElementById('recordingTimer');
        this.processingDelay = document.getElementById('processingDelay');
        this.audioSource = document.getElementById('audioSource');
        
        // 结果区域
        this.transcriptResults = document.getElementById('transcriptResults');
        this.resultCountElement = document.getElementById('resultCount');
        this.lastUpdateElement = document.getElementById('lastUpdate');
    }
    
    attachEventListeners() {
        this.startBtn.addEventListener('click', () => this.startSystemAudio());
        this.stopBtn.addEventListener('click', () => this.stopSystemAudio());
        this.clearBtn.addEventListener('click', () => this.clearResults());
        
        // 窗口关闭前记录录制状态
        window.addEventListener('beforeunload', () => {
            // 记录页面卸载前的录制状态
            this.wasRecordingBeforeUnload = this.isRecording;
            
            // 注意：这里我们不停止录制，只是记录状态
            if (this.websocket) {
                // 可以发送一个状态更新，但不停止录制
                try {
                    this.websocket.send(JSON.stringify({
                        type: 'page_unload',
                        wasRecording: this.isRecording,
                        timestamp: new Date().toISOString()
                    }));
                } catch (e) {
                    console.log('页面卸载时发送状态失败:', e);
                }
            }
        });
        
        // 页面可见性变化处理 - 修改：不再自动停止录制
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('页面隐藏，但系统音频录制继续运行');
                // 可以添加一些视觉提示，但不停止录制
                this.addSystemMessage('页面已隐藏，系统音频录制继续在后台运行', '系统状态');
            } else {
                console.log('页面恢复显示');
                // 页面恢复时，检查连接状态
                if (!this.isConnected && this.wasRecordingBeforeUnload) {
                    this.addSystemMessage('页面已恢复，重新连接中...', '系统状态');
                    this.initializeWebSocket();
                }
            }
        });
        
        // 新增：页面加载时检查是否需要恢复录制
        window.addEventListener('load', () => {
            // 可以在这里添加从本地存储恢复状态的逻辑
            console.log('页面加载完成');
        });
    }
    
    initializeWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${this.wsHost}:${this.wsPort}`;
        
        this.updateStatus('connecting', '连接中...');
        
        try {
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('WebSocket 连接已建立');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateStatus('connected', '已连接');
                this.connectionStatus.textContent = '已连接';
                this.connectionStatus.style.color = 'var(--success-color)';
                
                // 连接成功后，如果之前正在录制，尝试恢复录制
                if (this.wasRecordingBeforeUnload) {
                    this.addSystemMessage('连接已恢复，系统音频录制继续运行', '系统状态');
                    // 注意：这里我们不自动重新开始录制，因为后端可能还在录制
                    // 如果需要自动恢复，可以在这里发送开始录制的命令
                    // this.startSystemAudio();
                }
            };
            
            this.websocket.onmessage = (event) => {
                this.handleServerMessage(event.data, event);
            };
            
            this.websocket.onclose = (event) => {
                console.log('WebSocket 连接已关闭:', event);
                this.isConnected = false;
                this.updateStatus('offline', '连接断开');
                this.connectionStatus.textContent = '连接断开';
                this.connectionStatus.style.color = 'var(--danger-color)';
                
                // 注意：这里我们不自动停止录制，因为可能是暂时断开
                // 只在用户明确停止或页面关闭时才停止录制
                
                // 尝试重连
                this.handleReconnection();
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket 错误:', error);
                this.updateStatus('offline', '连接错误');
                this.connectionStatus.textContent = '连接错误';
                this.connectionStatus.style.color = 'var(--danger-color)';
            };
            
        } catch (error) {
            console.error('创建 WebSocket 连接失败:', error);
            this.handleReconnection();
        }
    }
    
    handleReconnection() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            
            console.log(`尝试重新连接... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            this.updateStatus('connecting', `重新连接中... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                if (!this.isConnected) {
                    this.initializeWebSocket();
                }
            }, delay);
        } else {
            console.error('达到最大重连次数，停止重连');
            this.updateStatus('offline', '连接失败');
            // 即使连接失败，也不自动停止录制，因为后端可能还在运行
        }
    }
    
    async startSystemAudio() {
        if (!this.isConnected) {
            alert('请等待连接建立后再开始系统音频');
            return;
        }
        
        if (this.isRecording) {
            console.log('系统音频录制已在运行中');
            return;
        }
        
        try {
            // 发送开始系统音频信号
            this.websocket.send(JSON.stringify({
                type: 'start_system_audio',
                sampleRate: 16000,
                timestamp: new Date().toISOString()
            }));
            
            console.log('已发送系统音频录制请求');
            
            // 添加等待消息
            this.addSystemMessage('正在启动系统音频服务...', '系统消息');
            
        } catch (error) {
            console.error('开始系统音频录制失败:', error);
            this.addErrorMessage(`无法开始系统音频录制: ${error.message}`);
            this.updateStatus('connected', '系统音频录制失败');
        }
    }
    
    stopSystemAudio() {
        if (this.isRecording && this.isConnected) {
            try {
                // 发送停止系统音频信号
                this.websocket.send(JSON.stringify({ 
                    type: 'stop_system_audio',
                    timestamp: new Date().toISOString()
                }));
            } catch (error) {
                console.error('发送停止信号失败:', error);
            }
        }
        
        // 更新本地状态
        this.isRecording = false;
        this.wasRecordingBeforeUnload = false;
        
        console.log('已发送系统音频停止请求');
        
        // 添加等待消息
        if (this.isConnected) {
            this.addSystemMessage('正在停止系统音频服务...', '系统消息');
        }
        
        // 更新UI
        this.updateUI('stopped');
        this.updateStatus('connected', '已连接');
        this.stopTimer();
    }
    
    handleServerMessage(message, event) {
        try {
            console.log('收到服务器消息，数据类型:', typeof message);
            
            // 处理二进制消息（音频数据）- 现在由后端直接处理，前端忽略
            if (message instanceof ArrayBuffer || message instanceof Blob) {
                console.log('收到二进制音频数据，前端忽略处理，由后端ASR服务处理');
                return;
            }
            
            // 处理文本消息
            if (typeof message === 'string') {
                // 检查消息是否为空
                if (!message || message.trim() === '') {
                    console.error('收到空消息');
                    this.addSystemMessage('收到空消息，连接可能有问题', '系统错误');
                    return;
                }
                
                const data = JSON.parse(message);
                const timestamp = new Date().toLocaleTimeString();
                
                console.log('解析后的数据:', data);
                
                switch(data.type) {
                    case 'status':
                        this.handleStatusMessage(data, timestamp);
                        break;
                        
                    case 'transcript':
                        this.handleTranscriptResult(data, timestamp);
                        break;
                        
                    case 'error':
                        this.handleErrorMessage(data, timestamp);
                        break;
                        
                    case 'pong':
                        // 心跳响应，无需处理
                        break;
                        
                    default:
                        console.log('未知消息类型:', data.type, '完整消息:', data);
                        this.addSystemMessage(`未知消息类型: ${data.type}`, '系统消息');
                }
            } else {
                console.log('未知的消息类型:', typeof message, message);
                this.addSystemMessage(`未知的消息格式: ${typeof message}`, '系统消息');
            }
            
        } catch (error) {
            console.error('解析服务器消息失败:', error);
            console.error('原始消息内容:', message);
            console.error('消息类型:', typeof message);
            
            // 提供更友好的错误信息
            let errorMsg = '解析服务器消息失败';
            if (error instanceof SyntaxError) {
                errorMsg = '服务器返回了无效的JSON格式';
            } else if (error instanceof TypeError) {
                errorMsg = '消息格式错误';
            }
            
            this.addErrorMessage(`${errorMsg}: ${error.message}`);
        }
    }
    
    handleStatusMessage(data, timestamp) {
        this.connectionStatus.textContent = data.message;
        
        // 根据消息内容更新录制状态
        if (data.message.includes('系统音频捕获已开始') || data.message.includes('系统音频录制已开始')) {
            this.isRecording = true;
            this.wasRecordingBeforeUnload = true; // 记录正在录制
            this.updateUI('recording');
            this.updateStatus('recording', '系统音频录制中...');
            this.startTimer();
            
            // 添加开始录制消息
            this.addSystemMessage('系统音频录制已开始', '开始录制');
        } else if (data.message.includes('系统音频录制已停止')) {
            this.isRecording = false;
            this.wasRecordingBeforeUnload = false; // 清除录制状态
            this.updateUI('stopped');
            this.updateStatus('connected', '已连接');
            this.stopTimer();
            
            // 添加停止录制消息
            this.addSystemMessage('系统音频录制已停止', '停止录制');
        }
        
        // 根据消息类型设置不同的样式
        if (data.message.includes('失败') || data.message.includes('错误')) {
            this.connectionStatus.style.color = 'var(--danger-color)';
        } else if (data.message.includes('开始') || data.message.includes('成功')) {
            this.connectionStatus.style.color = 'var(--success-color)';
        } else {
            this.connectionStatus.style.color = 'var(--info-color)';
        }
        
        // 只显示非录制状态相关的系统消息
        if (!data.message.includes('系统音频录制') && !data.message.includes('系统音频捕获')) {
            this.addSystemMessage(data.message, '系统状态');
        }
    }
    
    handleTranscriptResult(data, timestamp) {
        this.addTranscriptResult(data.text, timestamp, data.processing_time);
        this.updateProcessingDelay(data.processing_time);
        
        // 自动滚动到最新结果
        this.scrollToLatest();
    }
    
    handleErrorMessage(data, timestamp) {
        this.addErrorMessage(data.message, timestamp);
        
        // 如果是严重错误，停止录制
        if (data.message.includes('初始化失败') || data.message.includes('无法连接')) {
            this.isRecording = false;
            this.wasRecordingBeforeUnload = false;
            this.updateUI('stopped');
            this.updateStatus('connected', '已连接');
            this.stopTimer();
        }
    }
    
    addTranscriptResult(text, timestamp, processingTime) {
        this.resultCount++;
        
        const resultElement = document.createElement('div');
        resultElement.className = 'transcript-item success';
        
        resultElement.innerHTML = `
            <div class="transcript-header">
                <span class="timestamp">${timestamp}</span>
                <div>
                    <span class="system-audio-indicator">系统音频</span>
                    ${processingTime ? `<span class="processing-time">${processingTime.toFixed(2)}s</span>` : ''}
                </div>
            </div>
            <div class="transcript-text">${this.escapeHtml(text)}</div>
        `;
        
        this.appendResult(resultElement);
    }
    
    addSystemMessage(message, type = '系统消息') {
        const resultElement = document.createElement('div');
        resultElement.className = 'transcript-item info';
        
        resultElement.innerHTML = `
            <div class="transcript-header">
                <span class="timestamp">${new Date().toLocaleTimeString()}</span>
                <span class="processing-time">${type}</span>
            </div>
            <div class="transcript-text">${this.escapeHtml(message)}</div>
        `;
        
        this.appendResult(resultElement);
    }
    
    addErrorMessage(message, timestamp = new Date().toLocaleTimeString()) {
        const resultElement = document.createElement('div');
        resultElement.className = 'transcript-item error';
        
        resultElement.innerHTML = `
            <div class="transcript-header">
                <span class="timestamp">${timestamp}</span>
                <span class="processing-time">错误</span>
            </div>
            <div class="transcript-text">${this.escapeHtml(message)}</div>
        `;
        
        this.appendResult(resultElement);
    }
    
    appendResult(element) {
        // 移除空状态提示
        const emptyState = this.transcriptResults.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        this.transcriptResults.appendChild(element);
        this.updateResultStats();
        
        // 自动滚动到最新结果
        this.scrollToLatest();
    }
    
    scrollToLatest() {
        this.transcriptResults.scrollTop = this.transcriptResults.scrollHeight;
    }
    
    updateResultStats() {
        this.resultCountElement.textContent = `${this.resultCount} 条结果`;
        this.lastUpdateElement.textContent = `最后更新: ${new Date().toLocaleTimeString()}`;
    }
    
    updateProcessingDelay(delay) {
        if (delay) {
            const delayMs = (delay * 1000).toFixed(0);
            this.processingDelay.textContent = `${delayMs}ms`;
            this.processingDelay.style.color = delay < 1 ? 'var(--success-color)' : 
                                            delay < 2 ? 'var(--warning-color)' : 'var(--danger-color)';
        }
    }
    
    clearResults() {
        this.transcriptResults.innerHTML = `
            <div class="empty-state">
                <p>识别结果将显示在这里...</p>
                <p class="empty-hint">点击"开始系统音频"按钮开始捕获系统声音</p>
            </div>
        `;
        this.resultCount = 0;
        this.updateResultStats();
        this.processingDelay.textContent = '-';
        this.processingDelay.style.color = 'inherit';
    }
    
    startTimer() {
        this.recordingTime = 0;
        this.timerInterval = setInterval(() => {
            this.recordingTime++;
            const minutes = Math.floor(this.recordingTime / 60).toString().padStart(2, '0');
            const seconds = (this.recordingTime % 60).toString().padStart(2, '0');
            this.recordingTimer.textContent = `${minutes}:${seconds}`;
        }, 1000);
    }
    
    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        this.recordingTimer.textContent = '00:00';
    }
    
    updateUI(state) {
        switch(state) {
            case 'recording':
                this.startBtn.disabled = true;
                this.stopBtn.disabled = false;
                this.audioSource.textContent = '系统扬声器 (录制中)';
                this.audioSource.style.color = 'var(--danger-color)';
                break;
            case 'stopped':
                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                this.audioSource.textContent = '系统扬声器';
                this.audioSource.style.color = 'inherit';
                break;
            default:
                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                this.audioSource.textContent = '系统扬声器';
                this.audioSource.style.color = 'inherit';
        }
    }
    
    updateStatus(status, text) {
        this.statusIndicator.className = `indicator ${status}`;
        this.statusText.textContent = text;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // 发送心跳包保持连接
    startHeartbeat() {
        setInterval(() => {
            if (this.isConnected && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({
                    type: 'ping',
                    timestamp: new Date().toISOString()
                }));
            }
        }, 30000); // 每30秒发送一次心跳
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    const asr = new SystemAudioASR();
    
    // 启动心跳（可选）
    setTimeout(() => asr.startHeartbeat(), 10000);
    
    // 全局访问（用于调试）
    window.systemAudioASR = asr;
    
    // 添加键盘快捷键支持
    document.addEventListener('keydown', (event) => {
        // Ctrl+Enter 开始录制
        if (event.ctrlKey && event.key === 'Enter') {
            event.preventDefault();
            asr.startSystemAudio();
        }
        // Ctrl+Space 停止录制
        else if (event.ctrlKey && event.key === ' ') {
            event.preventDefault();
            asr.stopSystemAudio();
        }
        // Ctrl+Delete 清空结果
        else if (event.ctrlKey && event.key === 'Delete') {
            event.preventDefault();
            asr.clearResults();
        }
    });
    
    // 添加快捷键提示
    console.log('快捷键提示:');
    console.log('Ctrl+Enter - 开始系统音频录制');
    console.log('Ctrl+Space - 停止系统音频录制');
    console.log('Ctrl+Delete - 清空识别结果');
});