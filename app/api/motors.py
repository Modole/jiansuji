"""
电机配置管理API
"""
from flask import Blueprint, request, jsonify
from app.utils.database import execute_query, execute_many
from app.utils.helpers import create_response
import logging
import json

logger = logging.getLogger(__name__)
motors_bp = Blueprint('motors', __name__)


@motors_bp.route('/api/motors/custom', methods=['GET'])
def get_custom_motors():
    """获取所有自定义电机配置"""
    try:
        motors = execute_query(
            '''SELECT id, name, rated_voltage, rated_current, max_torque, 
                      rated_speed, pole_pairs, inertia, encoder_resolution,
                      created_at, updated_at 
               FROM custom_motors 
               ORDER BY created_at DESC''',
            fetch_all=True
        )
        
        motor_list = []
        for motor in motors:
            motor_list.append({
                'id': motor['id'],
                'name': motor['name'],
                'rated_voltage': motor['rated_voltage'],
                'rated_current': motor['rated_current'],
                'max_torque': motor['max_torque'],
                'rated_speed': motor['rated_speed'],
                'pole_pairs': motor['pole_pairs'],
                'inertia': motor['inertia'],
                'encoder_resolution': motor['encoder_resolution'],
                'created_at': motor['created_at'],
                'updated_at': motor['updated_at']
            })
        
        response_data, status_code = create_response(
            success=True,
            message="获取自定义电机列表成功",
            data=motor_list
        )
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"获取自定义电机列表失败: {e}")
        error_response, status_code = create_response(
            success=False,
            message="获取自定义电机列表失败",
            error=str(e)
        )
        return jsonify(error_response), status_code


@motors_bp.route('/api/motors/custom', methods=['POST'])
def create_custom_motor():
    """创建新的自定义电机配置"""
    try:
        data = request.get_json()
        if not data:
            error_response, status_code = create_response(
                success=False,
                message="请求数据不能为空"
            )
            return jsonify(error_response), status_code
        
        # 验证必需字段
        name = data.get('name', '').strip()
        if not name:
            error_response, status_code = create_response(
                success=False,
                message="电机名称不能为空"
            )
            return jsonify(error_response), status_code
        
        # 检查名称是否已存在
        existing = execute_query(
            'SELECT id FROM custom_motors WHERE name = ?',
            [name],
            fetch_one=True
        )
        if existing:
            error_response, status_code = create_response(
                success=False,
                message="电机名称已存在"
            )
            return jsonify(error_response), status_code
        
        # 插入新电机配置
        motor_id = execute_query(
            '''INSERT INTO custom_motors 
               (name, rated_voltage, rated_current, max_torque, rated_speed, 
                pole_pairs, inertia, encoder_resolution) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            [
                name,
                float(data.get('rated_voltage', 0)),
                float(data.get('rated_current', 0)),
                float(data.get('max_torque', 0)),
                float(data.get('rated_speed', 0)),
                int(data.get('pole_pairs', 0)),
                float(data.get('inertia', 0)),
                int(data.get('encoder_resolution', 0))
            ]
        )
        
        # 获取创建的电机信息
        motor = execute_query(
            '''SELECT id, name, rated_voltage, rated_current, max_torque, 
                      rated_speed, pole_pairs, inertia, encoder_resolution,
                      created_at, updated_at 
               FROM custom_motors WHERE id = last_insert_rowid()''',
            fetch_one=True
        )
        
        motor_data = {
            'id': motor['id'],
            'name': motor['name'],
            'rated_voltage': motor['rated_voltage'],
            'rated_current': motor['rated_current'],
            'max_torque': motor['max_torque'],
            'rated_speed': motor['rated_speed'],
            'pole_pairs': motor['pole_pairs'],
            'inertia': motor['inertia'],
            'encoder_resolution': motor['encoder_resolution'],
            'created_at': motor['created_at'],
            'updated_at': motor['updated_at']
        }
        
        response_data, status_code = create_response(
            success=True,
            message="创建自定义电机成功",
            data=motor_data
        )
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"创建自定义电机失败: {e}")
        error_response, status_code = create_response(
            success=False,
            message="创建自定义电机失败",
            error=str(e)
        )
        return jsonify(error_response), status_code


@motors_bp.route('/api/motors/custom/<int:motor_id>', methods=['PUT'])
def update_custom_motor(motor_id):
    """更新自定义电机配置"""
    try:
        data = request.get_json()
        if not data:
            error_response, status_code = create_response(
                success=False,
                message="请求数据不能为空"
            )
            return jsonify(error_response), status_code
        
        # 检查电机是否存在
        existing = execute_query(
            'SELECT id FROM custom_motors WHERE id = ?',
            [motor_id],
            fetch_one=True
        )
        if not existing:
            error_response, status_code = create_response(
                success=False,
                message="电机配置不存在"
            )
            return jsonify(error_response), status_code
        
        # 验证名称唯一性（排除当前电机）
        name = data.get('name', '').strip()
        if name:
            name_check = execute_query(
                'SELECT id FROM custom_motors WHERE name = ? AND id != ?',
                [name, motor_id],
                fetch_one=True
            )
            if name_check:
                error_response, status_code = create_response(
                    success=False,
                    message="电机名称已存在"
                )
                return jsonify(error_response), status_code
        
        # 更新电机配置
        execute_query(
            '''UPDATE custom_motors SET 
               name = ?, rated_voltage = ?, rated_current = ?, max_torque = ?, 
               rated_speed = ?, pole_pairs = ?, inertia = ?, encoder_resolution = ?,
               updated_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            [
                name or existing['name'],
                float(data.get('rated_voltage', 0)),
                float(data.get('rated_current', 0)),
                float(data.get('max_torque', 0)),
                float(data.get('rated_speed', 0)),
                int(data.get('pole_pairs', 0)),
                float(data.get('inertia', 0)),
                int(data.get('encoder_resolution', 0)),
                motor_id
            ]
        )
        
        # 获取更新后的电机信息
        motor = execute_query(
            '''SELECT id, name, rated_voltage, rated_current, max_torque, 
                      rated_speed, pole_pairs, inertia, encoder_resolution,
                      created_at, updated_at 
               FROM custom_motors WHERE id = ?''',
            [motor_id],
            fetch_one=True
        )
        
        motor_data = {
            'id': motor['id'],
            'name': motor['name'],
            'rated_voltage': motor['rated_voltage'],
            'rated_current': motor['rated_current'],
            'max_torque': motor['max_torque'],
            'rated_speed': motor['rated_speed'],
            'pole_pairs': motor['pole_pairs'],
            'inertia': motor['inertia'],
            'encoder_resolution': motor['encoder_resolution'],
            'created_at': motor['created_at'],
            'updated_at': motor['updated_at']
        }
        
        response_data, status_code = create_response(
            success=True,
            message="更新自定义电机成功",
            data=motor_data
        )
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"更新自定义电机失败: {e}")
        error_response, status_code = create_response(
            success=False,
            message="更新自定义电机失败",
            error=str(e)
        )
        return jsonify(error_response), status_code


@motors_bp.route('/api/motors/custom/<int:motor_id>', methods=['DELETE'])
def delete_custom_motor(motor_id):
    """删除自定义电机配置"""
    try:
        # 检查电机是否存在
        existing = execute_query(
            'SELECT id, name FROM custom_motors WHERE id = ?',
            [motor_id],
            fetch_one=True
        )
        if not existing:
            error_response, status_code = create_response(
                success=False,
                message="电机配置不存在"
            )
            return jsonify(error_response), status_code
        
        # 删除电机配置
        execute_query(
            'DELETE FROM custom_motors WHERE id = ?',
            [motor_id]
        )
        
        response_data, status_code = create_response(
            success=True,
            message=f"删除电机配置 '{existing['name']}' 成功"
        )
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"删除自定义电机失败: {e}")
        error_response, status_code = create_response(
            success=False,
            message="删除自定义电机失败",
            error=str(e)
        )
        return jsonify(error_response), status_code