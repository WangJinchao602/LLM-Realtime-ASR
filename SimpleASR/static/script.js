class AudioRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.recordingTime = 0;
        this.timerInterval = null;
        this.currentFilename = null;
        
        this.initializeElements();
        this.attachEventListeners();
    }
    
    initializeElements() {
        this.startBtn = document.getElementById('startRecord');
        this.stopBtn = document.getElementById('stopRecord');
        this.recognizeBtn = document.getElementById('recognizeBtn');
        this.status = document.getElementById('status');
        this.timer = document.getElementById('timer');
        this.audioPlayer = document.getElementById('audioPlayer');
        this.recordedAudio = document.getElementById('recordedAudio');
        this.resultSection = document.getElementById('resultSection');
        this.recognitionResult = document.getElementById('recognitionResult');
    }
    
    attachEventListeners() {
        this.startBtn.addEventListener('click', () => this.startRecording());
        this.stopBtn.addEventListener('click', () => this.stopRecording());
        this.recognizeBtn.addEventListener('click', () => this.recognizeSpeech());
    }
    
    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(stream, { 
                mimeType: 'audio/webm;codecs=opus' 
            });
            this.audioChunks = [];
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = () => {
                this.saveRecording();
                stream.getTracks().forEach(track => track.stop());
            };
            
            this.mediaRecorder.start();
            this.isRecording = true;
            this.startTimer();
            
            this.updateUI('recording');
            this.status.textContent = '正在录制...';
            
        } catch (error) {
            console.error('无法访问麦克风:', error);
            this.status.textContent = '无法访问麦克风，请检查权限设置';
        }
    }
    
    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.stopTimer();
            
            this.updateUI('stopped');
            this.status.textContent = '录制完成';
        }
    }
    
    startTimer() {
        this.recordingTime = 0;
        this.timerInterval = setInterval(() => {
            this.recordingTime++;
            const minutes = Math.floor(this.recordingTime / 60).toString().padStart(2, '0');
            const seconds = (this.recordingTime % 60).toString().padStart(2, '0');
            this.timer.textContent = `${minutes}:${seconds}`;
        }, 1000);
    }
    
    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
    }
    
    async saveRecording() {
        try {
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
            
            // 创建音频URL用于播放
            const audioUrl = URL.createObjectURL(audioBlob);
            this.recordedAudio.src = audioUrl;
            this.audioPlayer.style.display = 'block';
            
            // 上传到服务器
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
            
            const response = await fetch('/upload_audio', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.currentFilename = result.filename;
                this.recognizeBtn.disabled = false;
                this.status.textContent = '音频保存成功，可以点击语音识别按钮';
            } else {
                throw new Error(result.error);
            }
            
        } catch (error) {
            console.error('保存录音失败:', error);
            this.status.textContent = '保存录音失败: ' + error.message;
        }
    }
    
    async recognizeSpeech() {
        if (!this.currentFilename) {
            this.showResult('错误: 没有可识别的音频文件', 'error');
            return;
        }
        
        try {
            this.recognizeBtn.disabled = true;
            this.showResult('正在识别语音...', 'loading');
            
            const response = await fetch('/recognize_speech', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    filename: this.currentFilename
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showResult(result.result, 'success');
            } else {
                throw new Error(result.error);
            }
            
        } catch (error) {
            console.error('语音识别失败:', error);
            this.showResult('语音识别失败: ' + error.message, 'error');
        } finally {
            this.recognizeBtn.disabled = false;
        }
    }
    
    updateUI(state) {
        switch(state) {
            case 'recording':
                this.startBtn.disabled = true;
                this.stopBtn.disabled = false;
                this.recognizeBtn.disabled = true;
                break;
            case 'stopped':
                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                break;
            default:
                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                this.recognizeBtn.disabled = true;
        }
    }
    
    showResult(message, type = 'success') {
        this.resultSection.style.display = 'block';
        this.recognitionResult.textContent = message;
        this.recognitionResult.className = 'result-box';
        
        if (type === 'loading') {
            this.recognitionResult.classList.add('loading');
        } else if (type === 'error') {
            this.recognitionResult.classList.add('error');
        } else {
            this.recognitionResult.classList.add('success');
        }
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    new AudioRecorder();
});