#!/usr/bin/env python3
"""
调试版本的应用程序入口文件
"""
import os
import sys
import logging
from app import create_app

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def setup_logging():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('app_debug.log', encoding='utf-8')
        ]
    )

def debug_app_creation():
    """调试应用创建过程"""
    logger = logging.getLogger(__name__)
    
    logger.info("=== 开始创建Flask应用 ===")
    
    # 创建Flask应用
    app = create_app()
    
    logger.info(f"应用名称: {app.name}")
    logger.info(f"Blueprint数量: {len(app.blueprints)}")
    
    # 检查Blueprint注册
    logger.info("=== 已注册的Blueprint ===")
    for name, blueprint in app.blueprints.items():
        logger.info(f"  - {name}: {blueprint.name} (url_prefix: {blueprint.url_prefix})")
    
    # 检查路由注册
    logger.info("=== 已注册的路由 ===")
    with app.app_context():
        route_count = 0
        for rule in app.url_map.iter_rules():
            methods = list(rule.methods - {'HEAD', 'OPTIONS'})
            logger.info(f"  {rule.rule} -> {rule.endpoint} [{', '.join(methods)}]")
            route_count += 1
        logger.info(f"总路由数: {route_count}")
    
    # 测试特定路由
    logger.info("=== 测试特定路由 ===")
    with app.test_client() as client:
        test_routes = [
            '/health',
            '/debug/routes',
            '/debug/blueprints',
            '/api/motors/custom',
            '/api/settings/connection',
            '/api/settings',
            '/api/data/stats'
        ]
        
        for route in test_routes:
            try:
                response = client.get(route)
                status = "✓" if response.status_code == 200 else "✗"
                logger.info(f"  {status} {route}: {response.status_code}")
            except Exception as e:
                logger.error(f"  ✗ {route}: 错误 - {e}")
    
    return app

def main():
    """主函数"""
    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # 调试应用创建
        app = debug_app_creation()
        
        # 获取配置
        host = app.config.get('HOST', '127.0.0.1')
        port = app.config.get('PORT', 5001)  # 使用不同端口避免冲突
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
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()