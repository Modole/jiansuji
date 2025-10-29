"""
命令相关API蓝图
"""
import logging
from flask import Blueprint, request, jsonify
from app.services.node_red_service import NodeRedService
from app.utils.helpers import create_response, log_api_call, now_ms

logger = logging.getLogger(__name__)

bp = Blueprint('command', __name__)


@bp.route('/api/command/set/data', methods=['POST'])
def send_command():
    """发送命令到Node-RED"""
    start_time = now_ms()
    
    try:
        data = request.get_json()
        
        if not data:
            error_response, status_code = create_response(
                success=False,
                error="没有命令数据",
                message="请求体为空",
                status_code=400
            )
            return jsonify(error_response), status_code
        
        # 提取命令和参数
        command = data.get('command')
        if not command:
            error_response, status_code = create_response(
                success=False,
                error="缺少command字段",
                message="请求数据格式错误",
                status_code=400
            )
            return jsonify(error_response), status_code
        
        # 提取其他参数
        params = {k: v for k, v in data.items() if k != 'command'}
        
        # 创建命令日志（pending），返回ID
        log_id = NodeRedService.create_command_log(command, params)
        
        # 发送命令到Node-RED
        result = NodeRedService.send_command_to_node_red(command, params)
        
        # 完成命令日志（更新响应与状态）
        success = bool(result.get('success'))
        if log_id:
            NodeRedService.complete_command_log(log_id, result, success)
        else:
            # 兜底：旧方式记录最终状态
            NodeRedService.log_command(command, params, result, 'success' if success else 'failed')
        
        # 记录API调用
        duration = now_ms() - start_time
        log_api_call('/api/command/set/data', 'POST', data, result, duration)
        
        if success:
            response_data, status_code = create_response(
                success=True,
                data=result,
                message="命令发送成功"
            )
        else:
            response_data, status_code = create_response(
                success=False,
                error=result.get('error', 'unknown_error'),
                message=result.get('message', '命令发送失败'),
                status_code=502
            )
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"发送命令失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="发送命令失败",
            status_code=500
        )
        return jsonify(error_response), status_code


@bp.route('/api/command/history', methods=['GET'])
def get_command_history():
    """获取命令历史"""
    start_time = now_ms()
    
    try:
        # 获取查询参数
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 200)  # 限制最大查询数量
        
        # 获取命令历史
        history = NodeRedService.get_command_history(limit)
        
        # 记录API调用
        duration = now_ms() - start_time
        log_api_call('/api/commands/history', 'GET', {'limit': limit}, history, duration)
        
        response_data = {
            'history': history,
            'count': len(history),
            'limit': limit,
            'timestamp': now_ms()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"获取命令历史失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="获取命令历史失败",
            status_code=500
        )
        return jsonify(error_response), status_code


@bp.route('/api/command/node-red/test', methods=['GET'])
def test_node_red():
    """测试Node-RED连接"""
    start_time = now_ms()
    
    try:
        # 测试Node-RED连接
        test_result = NodeRedService.test_node_red_connection()
        
        # 记录API调用
        duration = now_ms() - start_time
        log_api_call('/api/node-red/test', 'GET', {}, test_result, duration)
        
        if test_result.get('success'):
            response_data, status_code = create_response(
                success=True,
                data=test_result,
                message="Node-RED连接正常"
            )
        else:
            response_data, status_code = create_response(
                success=False,
                error=test_result.get('error', 'connection_failed'),
                message=test_result.get('message', 'Node-RED连接失败'),
                status_code=503
            )
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"测试Node-RED连接失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="测试Node-RED连接失败",
            status_code=500
        )
        return jsonify(error_response), status_code


@bp.route('/api/command/batch', methods=['POST'])
def send_batch_commands():
    """批量发送命令"""
    start_time = now_ms()
    
    try:
        data = request.get_json()
        
        if not data or 'commands' not in data:
            error_response, status_code = create_response(
                success=False,
                error="缺少commands数组",
                message="请求数据格式错误",
                status_code=400
            )
            return jsonify(error_response), status_code
        
        commands = data['commands']
        if not isinstance(commands, list):
            error_response, status_code = create_response(
                success=False,
                error="commands必须是数组",
                message="请求数据格式错误",
                status_code=400
            )
            return jsonify(error_response), status_code
        
        results = []
        success_count = 0
        
        # 逐个执行命令
        for cmd_data in commands:
            if not isinstance(cmd_data, dict) or 'command' not in cmd_data:
                results.append({
                    'success': False,
                    'error': 'invalid_command_format',
                    'message': '命令格式错误'
                })
                continue
            
            command = cmd_data['command']
            params = {k: v for k, v in cmd_data.items() if k != 'command'}
            
            # 发送单个命令
            result = NodeRedService.send_command_to_node_red(command, params)
            results.append(result)
            
            if result.get('success'):
                success_count += 1
        
        # 记录API调用
        duration = now_ms() - start_time
        log_api_call('/api/commands/batch', 'POST', data, results, duration)
        
        response_data = {
            'results': results,
            'total': len(commands),
            'success_count': success_count,
            'failed_count': len(commands) - success_count,
            'timestamp': now_ms()
        }
        
        # 如果所有命令都成功，返回200；否则返回207（部分成功）
        status_code = 200 if success_count == len(commands) else 207
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"批量发送命令失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="批量发送命令失败",
            status_code=500
        )
        return jsonify(error_response), status_code