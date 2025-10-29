"""
谐波减速机测试系统 Flask 应用
"""
import os
from flask import Flask, request
from flask_cors import CORS
import logging

from app.config import Config
from app.utils.database import init_db


def create_app(config_class=Config):
    """应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 启用CORS
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # 注册蓝图
    from app.api.data import bp as data_bp
    from app.api.command import bp as command_bp
    from app.api.export import bp as export_bp
    from app.api.settings import bp as settings_bp
    from app.api.motors import motors_bp
    
    app.register_blueprint(data_bp)
    app.register_blueprint(command_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(motors_bp)
    
    # 静态文件路由
    @app.route('/')
    def index():
        return app.send_static_file('templates/index.html')
    
    @app.route('/<path:filename>')
    def static_files(filename):
        return app.send_static_file(filename)
    
    # 健康检查
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'harmonic-reducer-test'}
    
    # 全局请求日志
    logger = logging.getLogger('request')
    
    @app.before_request
    def _log_request():
        if app.config.get('DEBUG', False):
            print(f"[REQ] {request.method} {request.path}")
        logger.info(f"请求: {request.method} {request.path}")
    
    # 调试路由 - 显示所有注册的路由
    @app.route('/debug/routes')
    def debug_routes():
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
                'rule': str(rule)
            })
        return {'routes': routes, 'count': len(routes)}
    
    # 调试路由 - 显示所有Blueprint
    @app.route('/debug/blueprints')
    def debug_blueprints():
        blueprints = {}
        for name, blueprint in app.blueprints.items():
            blueprints[name] = {
                'name': blueprint.name,
                'url_prefix': blueprint.url_prefix,
                'static_folder': blueprint.static_folder,
                'template_folder': blueprint.template_folder
            }
        return {'blueprints': blueprints, 'count': len(blueprints)}
    
    # 初始化数据库
    with app.app_context():
        init_db()
    
    return app