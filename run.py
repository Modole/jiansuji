#!/usr/bin/env python3
"""
应用程序入口文件
"""
import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from app import create_app

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def setup_logging(app):
    """设置日志配置：按日滚动保留30天，默认降级到WARNING"""
    log_level_name = app.config.get('LOG_LEVEL', 'WARNING').upper()
    log_level = getattr(logging, log_level_name, logging.WARNING)

    # 重置根logger
    root = logging.getLogger()
    root.handlers = []
    root.setLevel(log_level)

    # 格式
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # 文件日志：每日轮转，保留30天
    log_file = app.config.get('LOG_FILE', os.path.join(project_root, 'logs', 'app.log'))
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    file_handler = TimedRotatingFileHandler(log_file, when='D', interval=1, backupCount=30, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # 控制台日志：仅输出ERROR以减少噪音
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.ERROR)
    console.setFormatter(fmt)
    root.addHandler(console)

    # 降低Werkzeug日志
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    # 保留关键模块的INFO（数据与Node-RED交互）
    logging.getLogger('app.api.data').setLevel(logging.INFO)
    logging.getLogger('app.services.node_red_service').setLevel(logging.INFO)
    logging.getLogger('app.services.data_service').setLevel(logging.INFO)

def main():
    """主函数"""
    logger = logging.getLogger(__name__)
    
    try:
        # 创建Flask应用
        app = create_app()
        # 设置日志（使用应用配置）
        setup_logging(app)

        # 基本信息（不打印冗长路由/蓝图清单）
        logger.info(f"应用名称: {app.name}")
        
        # 获取配置
        host = app.config.get('HOST', '127.0.0.1')
        port = app.config.get('PORT', 5000)
        debug = app.config.get('DEBUG', False)
        
        logger.info(f"启动应用程序...")
        logger.info(f"环境: {app.config.get('ENV', 'development')}")
        logger.info(f"调试模式: {debug}")
        logger.info(f"服务地址: http://{host}:{port}")
        
        # 启动应用
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"启动应用失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()