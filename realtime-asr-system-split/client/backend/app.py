from flask import Flask, render_template
import logging
from config.config import ClientConfig

logger = logging.getLogger(__name__)

app = Flask(__name__, 
           template_folder='../frontend',
           static_folder='../frontend')
app.config['SECRET_KEY'] = ClientConfig.SECRET_KEY

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

if __name__ == '__main__':
    logger.info("启动客户端 Flask 应用...")
    app.run(
        host=ClientConfig.FLASK_HOST, 
        port=ClientConfig.FLASK_PORT, 
        debug=True
    )