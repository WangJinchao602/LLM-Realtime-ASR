import os
import base64
import uuid
from flask import Flask, render_template, request, jsonify, send_from_directory
import openai

app = Flask(__name__)
app.config['CACHE_FOLDER'] = 'cache'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 创建cache文件夹
if not os.path.exists(app.config['CACHE_FOLDER']):
    os.makedirs(app.config['CACHE_FOLDER'])

# 初始化OpenAI客户端（请替换为你的API配置）
client = openai.OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"  # 如果需要自定义API端点
)

def encode_audio(audio_file_path):
    """将音频文件编码为base64"""
    with open(audio_file_path, 'rb') as audio_file:
        return base64.b64encode(audio_file.read()).decode('utf-8')

def speech_to_text(audio_file_path):
    """语音识别函数"""
    try:
        base64_audio = encode_audio(audio_file_path)
        
        # 这里使用你提供的语音识别代码
        completion = client.chat.completions.create(
            model="qwen3-omni-30b-a3b-captioner",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": f"data:;base64,{base64_audio}"
                            },
                        }
                    ],
                }
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"语音识别失败: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    """接收上传的音频文件"""
    try:
        if 'audio' not in request.files:
            return jsonify({'error': '没有音频文件'}), 400
        
        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({'error': '未选择文件'}), 400
        
        # 生成唯一文件名
        filename = f"recording_{uuid.uuid4().hex}.wav"
        file_path = os.path.join(app.config['CACHE_FOLDER'], filename)
        
        # 保存音频文件
        audio_file.save(file_path)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'message': '音频保存成功'
        })
        
    except Exception as e:
        return jsonify({'error': f'上传失败: {str(e)}'}), 500

@app.route('/recognize_speech', methods=['POST'])
def recognize_speech():
    """语音识别接口"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        
        if not filename:
            return jsonify({'error': '缺少文件名参数'}), 400
        
        file_path = os.path.join(app.config['CACHE_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': '音频文件不存在'}), 404
        
        # 调用语音识别
        recognition_result = speech_to_text(file_path)
        
        return jsonify({
            'success': True,
            'result': recognition_result
        })
        
    except Exception as e:
        return jsonify({'error': f'识别失败: {str(e)}'}), 500

@app.route('/cache/<filename>')
def get_audio_file(filename):
    """提供音频文件访问"""
    return send_from_directory(app.config['CACHE_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)