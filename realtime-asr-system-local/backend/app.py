from flask import Flask, render_template, request
import logging
from config.config import Config

# 配置日志
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
           template_folder='../frontend/templates',
           static_folder='../frontend/static')
app.config['SECRET_KEY'] = Config.SECRET_KEY

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

if __name__ == '__main__':
    logger.info("启动 Flask 应用...")
    app.run(host='0.0.0.0', port=5000, debug=True)