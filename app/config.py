"""
应用配置管理
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.parent


class Config:
    """基础配置"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # 数据库配置
    DATABASE_PATH = os.environ.get('DATABASE_PATH') or str(BASE_DIR / 'data' / 'database' / 'data.db')
    
    # Node-RED配置
    NODE_RED_BASE_URL = os.environ.get('NODE_RED_BASE_URL', 'http://127.0.0.1:1880')
    NODE_RED_TIMEOUT = int(os.environ.get('NODE_RED_TIMEOUT', '5'))
    
    # 服务器配置
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', '5000'))
    
    # 导出配置
    EXPORT_DIR = os.environ.get('EXPORT_DIR') or str(BASE_DIR / 'data' / 'exports')
    
    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE') or str(BASE_DIR / 'logs' / 'app.log')
    
    @staticmethod
    def init_app(app):
        """初始化应用配置"""
        # 确保必要的目录存在
        os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
        os.makedirs(Config.EXPORT_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(Config.LOG_FILE), exist_ok=True)


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    DATABASE_PATH = ':memory:'  # 使用内存数据库


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}