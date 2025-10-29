import os
import json
import logging
from flask import Blueprint, request, jsonify, current_app
from app.utils.database import execute_query
from app.utils.helpers import create_response

logger = logging.getLogger(__name__)

bp = Blueprint('settings', __name__)

DEFAULT_SETTINGS = {
    "model": "Custom",
    "rated_voltage": 48,
    "rated_current": 5.0,
    "max_torque_nm": 2.5,
    "rated_speed_rpm": 3000,
    "pole_pairs": 4,
    "inertia_kgm2": 0.000015,
    "encoder_resolution": 2048
}


def _settings_file_path():
    try:
        data_dir = os.path.abspath(os.path.join(current_app.root_path, '..', 'data'))
    except Exception:
        # 兜底：按照项目结构推断
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        data_dir = os.path.join(base, 'data')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'settings.json')


def _load_settings():
    path = _settings_file_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return { **DEFAULT_SETTINGS, **data }
        except Exception as e:
            logger.warning('读取设置失败: %s', e)
    return DEFAULT_SETTINGS.copy()


def _save_settings(data: dict):
    path = _settings_file_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error('保存设置失败: %s', e)
        return False


@bp.route('/api/settings', methods=['GET'])
def get_settings():
    """
    获取当前设置（若不存在则返回默认值）
    """
    settings = _load_settings()
    env = 'production' if not current_app.config.get('DEBUG', False) else 'development'
    return jsonify({
        "success": True,
        "settings": settings,
        "env": env,
        "debug": current_app.config.get('DEBUG', False)
    }), 200


@bp.route('/api/settings', methods=['POST'])
def save_settings():
    """
    保存设置到服务器（data/settings.json），并返回最新设置
    """
    try:
        payload = request.get_json(force=True) or {}
        incoming = payload.get('settings') if isinstance(payload, dict) else None
        if not isinstance(incoming, dict):
            return jsonify({
                "success": False,
                "error": "invalid_settings",
                "message": "请求体中缺少有效的settings字段"
            }), 400
        merged = { **DEFAULT_SETTINGS, **incoming }
        if not _save_settings(merged):
            return jsonify({
                "success": False,
                "error": "save_failed",
                "message": "服务器保存设置失败"
            }), 500
        return jsonify({
            "success": True,
            "settings": merged
        }), 200
    except Exception as e:
        logger.exception('保存设置异常')
        return jsonify({
            "success": False,
            "error": "exception",
            "message": str(e)
        }), 500


@bp.route('/api/settings/reset', methods=['POST'])
def reset_settings():
    """
    重置为默认设置
    """
    ok = _save_settings(DEFAULT_SETTINGS.copy())
    if not ok:
        return jsonify({
            "success": False,
            "error": "save_failed",
            "message": "服务器保存设置失败"
        }), 500
    return jsonify({
        "success": True,
        "settings": DEFAULT_SETTINGS
    }), 200


# 数据库配置管理API
@bp.route('/api/settings/connection', methods=['GET'])
def get_connection_settings():
    """获取数据连接配置"""
    try:
        settings = execute_query(
            '''SELECT config_key, config_value, updated_at 
               FROM system_config 
               WHERE config_key IN ('data_collection_url', 'data_write_url')
               ORDER BY config_key''',
            fetch_all=True
        )
        
        config_data = {}
        for setting in settings:
            config_data[setting['config_key']] = {
                'value': setting['config_value'],
                'updated_at': setting['updated_at']
            }
        
        # 如果没有配置，返回默认值
        if not config_data:
            config_data = {
                'data_collection_url': {
                    'value': 'http://localhost:1880/data/collect',
                    'updated_at': None
                },
                'data_write_url': {
                    'value': 'http://localhost:1880/data/write',
                    'updated_at': None
                }
            }
        
        response_data, status_code = create_response(
            success=True,
            message="获取连接配置成功",
            data=config_data
        )
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"获取连接配置失败: {e}")
        error_response, status_code = create_response(
            success=False,
            message="获取连接配置失败",
            error=str(e)
        )
        return jsonify(error_response), status_code


@bp.route('/api/settings/connection', methods=['POST'])
def update_connection_settings():
    """更新数据连接配置"""
    try:
        data = request.get_json()
        if not data:
            error_response, status_code = create_response(
                success=False,
                message="请求数据不能为空"
            )
            return jsonify(error_response), status_code
        
        # 验证URL格式
        data_collection_url = data.get('data_collection_url', '').strip()
        data_write_url = data.get('data_write_url', '').strip()
        
        if not data_collection_url or not data_write_url:
            error_response, status_code = create_response(
                success=False,
                message="数据采集URL和数据写入URL不能为空"
            )
            return jsonify(error_response), status_code
        
        # 简单的URL格式验证
        if not (data_collection_url.startswith('http://') or data_collection_url.startswith('https://')):
            error_response, status_code = create_response(
                success=False,
                message="数据采集URL格式不正确"
            )
            return jsonify(error_response), status_code
            
        if not (data_write_url.startswith('http://') or data_write_url.startswith('https://')):
            error_response, status_code = create_response(
                success=False,
                message="数据写入URL格式不正确"
            )
            return jsonify(error_response), status_code
        
        # 更新或插入配置
        configs = [
            ('data_collection_url', data_collection_url),
            ('data_write_url', data_write_url)
        ]
        
        for config_key, config_value in configs:
            # 检查配置是否存在
            existing = execute_query(
                'SELECT id FROM system_config WHERE config_key = ?',
                [config_key],
                fetch_one=True
            )
            
            if existing:
                # 更新现有配置
                execute_query(
                    '''UPDATE system_config 
                       SET config_value = ?, updated_at = CURRENT_TIMESTAMP 
                       WHERE config_key = ?''',
                    [config_value, config_key]
                )
            else:
                # 插入新配置
                execute_query(
                    '''INSERT INTO system_config (config_key, config_value) 
                       VALUES (?, ?)''',
                    [config_key, config_value]
                )
        
        # 获取更新后的配置
        updated_settings = execute_query(
            '''SELECT config_key, config_value, updated_at 
               FROM system_config 
               WHERE config_key IN ('data_collection_url', 'data_write_url')
               ORDER BY config_key''',
            fetch_all=True
        )
        
        config_data = {}
        for setting in updated_settings:
            config_data[setting['config_key']] = {
                'value': setting['config_value'],
                'updated_at': setting['updated_at']
            }
        
        response_data, status_code = create_response(
            success=True,
            message="更新连接配置成功",
            data=config_data
        )
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"更新连接配置失败: {e}")
        error_response, status_code = create_response(
            success=False,
            message="更新连接配置失败",
            error=str(e)
        )
        return jsonify(error_response), status_code


@bp.route('/api/settings/test-connection', methods=['POST'])
def test_connection():
    """测试数据连接"""
    try:
        data = request.get_json()
        if not data:
            error_response, status_code = create_response(
                success=False,
                message="请求数据不能为空"
            )
            return jsonify(error_response), status_code
        
        url = data.get('url', '').strip()
        if not url:
            error_response, status_code = create_response(
                success=False,
                message="测试URL不能为空"
            )
            return jsonify(error_response), status_code
        
        # 这里可以添加实际的连接测试逻辑
        # 目前返回模拟结果
        import requests
        import time
        
        try:
            start_time = time.time()
            response = requests.get(url, timeout=5)
            end_time = time.time()
            
            response_time = round((end_time - start_time) * 1000, 2)  # 毫秒
            
            if response.status_code == 200:
                test_result = {
                    'success': True,
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'message': '连接测试成功'
                }
            else:
                test_result = {
                    'success': False,
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'message': f'连接测试失败，状态码: {response.status_code}'
                }
                
        except requests.exceptions.Timeout:
            test_result = {
                'success': False,
                'status_code': None,
                'response_time': None,
                'message': '连接超时'
            }
        except requests.exceptions.ConnectionError:
            test_result = {
                'success': False,
                'status_code': None,
                'response_time': None,
                'message': '连接失败，无法访问目标地址'
            }
        except Exception as e:
            test_result = {
                'success': False,
                'status_code': None,
                'response_time': None,
                'message': f'连接测试异常: {str(e)}'
            }
        
        response_data, status_code = create_response(
            success=True,
            message="连接测试完成",
            data=test_result
        )
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"连接测试失败: {e}")
        error_response, status_code = create_response(
            success=False,
            message="连接测试失败",
            error=str(e)
        )
        return jsonify(error_response), status_code