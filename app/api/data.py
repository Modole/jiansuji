"""
数据相关API蓝图
"""
import logging
from flask import Blueprint, request, jsonify
from app.services.data_service import DataService
from app.services.node_red_service import NodeRedService
from app.utils.helpers import create_response, log_api_call, now_ms

logger = logging.getLogger(__name__)

bp = Blueprint('data', __name__)


@bp.route('/api/data/measurements', methods=['POST'])
def get_datas():
    """获取测量数据"""
    start_time = now_ms()
    
    try:
        # 尝试从Node-RED获取最新数据
        node_red_data = NodeRedService.fetch_data_from_node_red()
        hysteresis_meta = {'saved': False, 'point_count': 0, 'timestamp': None}
        
        if node_red_data:
            # 如果从Node-RED获取到数据，保存到数据库（指标类）
            DataService.save_measurement_data(node_red_data)
            
            # 额外：保存Node-RED提供的滞回曲线（如存在）
            try:
                hyst = node_red_data.get('hysteresis_curve')
                if isinstance(hyst, dict):
                    raw_points = hyst.get('points')
                    ts = hyst.get('timestamp')
                    hysteresis_meta['timestamp'] = ts
                    normalized_points = []
                    
                    def _pick_val(obj, keys):
                        for k in keys:
                            if k in obj:
                                try:
                                    return float(obj[k])
                                except (TypeError, ValueError):
                                    continue
                        return None
                    
                    if isinstance(raw_points, list):
                        for p in raw_points:
                            if not isinstance(p, dict):
                                continue
                            # 支持 angle/torque 原始键或候选键名映射
                            angle_val = p.get('angle')
                            torque_val = p.get('torque')
                            if angle_val is None:
                                angle_val = _pick_val(p, ['position_deg', 'position', 'theta', 'angle_deg', 'angular_position'])
                            if torque_val is None:
                                torque_val = _pick_val(p, ['torque_nm', 'torque', 'load_torque', 'current_torque', 'torque_Nm'])
                            if angle_val is not None and torque_val is not None:
                                normalized_points.append({'angle': angle_val, 'torque': torque_val})
                    
                    if normalized_points:
                        DataService.save_hysteresis_data(normalized_points, curve_type='hysteresis', timestamp=ts)
                        hysteresis_meta['saved'] = True
                        hysteresis_meta['point_count'] = len(normalized_points)
            except Exception as e:
                logger.warning(f"保存Node-RED滞回曲线失败: {e}")
            
            result_data = node_red_data
            data_source = 'node_red'
        else:
            # 如果Node-RED不可用，从数据库获取最新数据
            logger.info("Node-RED不可用，从数据库获取数据")
            result_data = DataService.get_current_measurements()
            data_source = 'database'
        
        # 记录API调用
        duration = now_ms() - start_time
        log_api_call('/api/data/measurements', 'POST', {}, result_data, duration)
        
        # 添加元数据
        response_data = {
            **result_data,
            '_meta': {
                'source': data_source,
                'timestamp': now_ms(),
                'count': len(result_data)
            }
        }
        if hysteresis_meta['saved']:
            response_data['_hysteresis'] = hysteresis_meta
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"获取数据失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="获取数据失败",
            status_code=500
        )
        return jsonify(error_response), status_code


@bp.route('/api/data/ingest', methods=['POST'])
def ingest_data():
    """数据入库接口（供Node-RED推送数据使用）"""
    start_time = now_ms()
    
    try:
        data = request.get_json()
        
        if not data:
            error_response, status_code = create_response(
                success=False,
                error="没有数据",
                message="请求体为空",
                status_code=400
            )
            return jsonify(error_response), status_code
        
        # 保存数据到数据库
        success = DataService.save_measurement_data(data)
        
        if success:
            # 记录API调用
            duration = now_ms() - start_time
            log_api_call('/api/ingest', 'POST', data, {'success': True}, duration)
            
            response_data, status_code = create_response(
                success=True,
                data={'saved': True, 'count': len(data)},
                message="数据保存成功"
            )
        else:
            response_data, status_code = create_response(
                success=False,
                error="保存失败",
                message="数据保存失败",
                status_code=500
            )
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"数据入库失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="数据入库失败",
            status_code=500
        )
        return jsonify(error_response), status_code


@bp.route('/api/data/hysteresis', methods=['GET'])
def get_hysteresis():
    """获取滞回曲线数据"""
    start_time = now_ms()
    
    try:
        # 获取滞回曲线数据
        points = DataService.get_hysteresis_curve_data()
        
        # 分析曲线特性
        analysis = DataService.analyze_hysteresis_curve(points)
        
        # 记录API调用
        duration = now_ms() - start_time
        log_api_call('/api/data/hysteresis', 'GET', {}, points, duration)
        
        response_data = {
            'points': points,
            'analysis': analysis,
            'count': len(points),
            'timestamp': now_ms()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"获取滞回曲线数据失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="获取滞回曲线数据失败",
            status_code=500
        )
        return jsonify(error_response), status_code


@bp.route('/api/data/hysteresis', methods=['POST'])
def save_hysteresis():
    """保存滞回曲线数据"""
    start_time = now_ms()
    
    try:
        data = request.get_json()
        
        if not data or 'points' not in data:
            error_response, status_code = create_response(
                success=False,
                error="缺少points数据",
                message="请求数据格式错误",
                status_code=400
            )
            return jsonify(error_response), status_code
        
        raw_points = data['points']
        timestamp = data.get('timestamp')
        curve_type = data.get('curve_type', 'hysteresis')
        
        # 兼容不同键名的点格式，将其标准化为 {angle, torque}
        normalized_points = []
        
        def _pick_val(obj, keys):
            for k in keys:
                if k in obj:
                    try:
                        return float(obj[k])
                    except (TypeError, ValueError):
                        continue
            return None
        
        if isinstance(raw_points, list):
            for p in raw_points:
                if not isinstance(p, dict):
                    continue
                angle_val = p.get('angle')
                torque_val = p.get('torque')
                if angle_val is None:
                    angle_val = _pick_val(p, ['position_deg', 'position', 'theta', 'angle_deg', 'angular_position'])
                if torque_val is None:
                    torque_val = _pick_val(p, ['torque_nm', 'torque', 'load_torque', 'current_torque', 'torque_Nm'])
                if angle_val is not None and torque_val is not None:
                    normalized_points.append({'angle': angle_val, 'torque': torque_val})
        
        # 保存滞回曲线数据
        success = False
        if normalized_points:
            success = DataService.save_hysteresis_data(normalized_points, curve_type=curve_type, timestamp=timestamp)
        
        if success:
            # 记录API调用
            duration = now_ms() - start_time
            log_api_call('/api/data/hysteresis', 'POST', data, {'success': True}, duration)
            
            response_data, status_code = create_response(
                success=True,
                data={'saved': True, 'count': len(normalized_points)},
                message="滞回曲线数据保存成功"
            )
        else:
            response_data, status_code = create_response(
                success=False,
                error="保存失败",
                message="滞回曲线数据保存失败",
                status_code=500
            )
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"保存滞回曲线数据失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="保存滞回曲线数据失败",
            status_code=500
        )
        return jsonify(error_response), status_code


@bp.route('/api/data/collect', methods=['POST'])
def collect_data():
    """数据采集接口（仅Node-RED实时数据）"""
    start_time = now_ms()
    
    try:
        data = request.get_json() or {}
        keys = data.get('keys', [])
        
        # 从 Node-RED 获取实时测量数据
        values = NodeRedService.fetch_data_from_node_red() or {}
        
        # 如果指定了 keys，仅返回指定项
        if keys:
            values = {k: v for k, v in values.items() if k in keys}
        
        # 记录API调用
        duration = now_ms() - start_time
        log_api_call('/api/data/collect', 'POST', data, values, duration)
        
        response_data, status_code = create_response(
            success=True,
            data={'values': values, '_meta': {'source': 'node_red', 'timestamp': now_ms(), 'count': len(values)}},
            message="Node-RED实时数据"
        )
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"数据采集失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="数据采集失败",
            status_code=500
        )
        return jsonify(error_response), status_code


@bp.route('/api/data/write', methods=['POST'])
def write_data():
    """数据写入接口（向PLC写入电机配置）"""
    start_time = now_ms()
    
    try:
        data = request.get_json()
        
        if not data:
            error_response, status_code = create_response(
                success=False,
                error="没有数据",
                message="请求体为空",
                status_code=400
            )
            return jsonify(error_response), status_code
        
        motor_config = data.get('motor_config', {})
        test_config = data.get('test_config', {})
        addresses = data.get('addresses', {})
        
        # 模拟写入操作（实际应写入PLC）
        write_results = {}
        written_count = 0
        failed_count = 0
        
        # 处理电机配置参数
        motor_params = {
            'motor_model': motor_config.get('model'),
            'rated_voltage': motor_config.get('rated_voltage'),
            'rated_current': motor_config.get('rated_current'),
            'max_torque': motor_config.get('max_torque_nm'),
            'rated_speed': motor_config.get('rated_speed_rpm'),
            'pole_pairs': motor_config.get('pole_pairs'),
            'inertia': motor_config.get('inertia_kgm2'),
            'encoder_res': motor_config.get('encoder_resolution')
        }
        
        # 处理测试配置参数
        test_params = {
            'test_type': test_config.get('test_type'),
            'load_level': test_config.get('load_level'),
            'test_speed': test_config.get('speed_rpm'),
            'test_duration': test_config.get('duration_seconds')
        }
        
        # 合并所有参数
        all_params = {**motor_params, **test_params}
        
        # 默认地址映射
        default_addresses = {
            'motor_model': 'D3001',
            'rated_voltage': 'D3002',
            'rated_current': 'D3003',
            'max_torque': 'D3004',
            'rated_speed': 'D3005',
            'pole_pairs': 'D3006',
            'inertia': 'D3007',
            'encoder_res': 'D3008',
            'test_type': 'D3101',
            'load_level': 'D3102',
            'test_speed': 'D3103',
            'test_duration': 'D3104'
        }
        
        # 使用提供的地址或默认地址
        addr_map = {**default_addresses, **addresses}
        
        # 模拟写入每个参数
        import random
        for param_name, param_value in all_params.items():
            if param_value is not None:
                addr = addr_map.get(param_name, f'D{3000 + len(write_results)}')
                
                # 模拟写入成功/失败（90%成功率）
                if random.random() < 0.9:
                    write_results[param_name] = {
                        'addr': addr,
                        'status': 'success'
                    }
                    written_count += 1
                else:
                    write_results[param_name] = {
                        'addr': addr,
                        'status': 'failed',
                        'error': '写入超时'
                    }
                    failed_count += 1
        
        # 记录API调用
        duration = now_ms() - start_time
        log_api_call('/api/data/write', 'POST', data, write_results, duration)
        
        if failed_count == 0:
            response_data, status_code = create_response(
                success=True,
                data={
                    'written_parameters': written_count,
                    'failed_parameters': failed_count,
                    'write_results': write_results
                },
                message="配置写入成功"
            )
        else:
            response_data, status_code = create_response(
                success=False,
                data={
                    'written_parameters': written_count,
                    'failed_parameters': failed_count,
                    'write_results': write_results
                },
                error="部分参数写入失败",
                message=f"成功写入{written_count}个参数，{failed_count}个参数写入失败",
                status_code=207  # 207 Multi-Status
            )
        
        return jsonify(response_data), status_code
        
    except Exception as e:
        logger.error(f"数据写入失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="数据写入失败",
            status_code=500
        )
        return jsonify(error_response), status_code


@bp.route('/api/data/stats', methods=['GET'])
def get_statistics():
    """获取数据统计信息"""
    start_time = now_ms()
    
    try:
        stats = DataService.get_data_statistics()
        
        # 记录API调用
        duration = now_ms() - start_time
        log_api_call('/api/stats', 'GET', {}, stats, duration)
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="获取统计信息失败",
            status_code=500
        )
        return jsonify(error_response), status_code


@bp.route('/api/data/history/<key>', methods=['GET'])
def get_measurement_history(key):
    """获取指定测量项的历史数据"""
    start_time = now_ms()
    
    try:
        # 获取查询参数
        limit = request.args.get('limit', 100, type=int)
        limit = min(limit, 1000)  # 限制最大查询数量
        
        # 获取历史数据
        history = DataService.get_measurement_history(key, limit)
        
        # 记录API调用
        duration = now_ms() - start_time
        log_api_call(f'/api/history/{key}', 'GET', {'limit': limit}, history, duration)
        
        response_data = {
            'key': key,
            'history': history,
            'count': len(history),
            'limit': limit,
            'timestamp': now_ms()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"获取历史数据失败: {e}")
        error_response, status_code = create_response(
            success=False,
            error=str(e),
            message="获取历史数据失败",
            status_code=500
        )
        return jsonify(error_response), status_code


@bp.route('/api/data/current', methods=['GET'])
def get_current_data():
  start_time = now_ms()
  try:
    values = NodeRedService.fetch_data_from_node_red() or {}

    def _extract_numeric(val):
      if isinstance(val, dict):
        for key in ('value','val','data','v','current'):
          if key in val:
            try:
              return float(val[key])
            except (TypeError, ValueError):
              continue
        for _, v in val.items():
          try:
            return float(v)
          except (TypeError, ValueError):
            continue
        return None
      # 字符串中提取第一个数字（兼容如 "12.34 deg"）
      if isinstance(val, str):
        try:
          import re
          m = re.search(r"-?\d+(?:\.\d+)?", val)
          if m:
            return float(m.group(0))
        except Exception:
          pass
        return None
      try:
        return float(val)
      except (TypeError, ValueError):
        return None

    def _find_numeric_deep(obj, alias_keys, substrings):
      try:
        if obj is None:
          return None
        # 字典：先匹配当前层键，再递归子结构
        if isinstance(obj, dict):
          for k, v in obj.items():
            k_lower = str(k).lower()
            if k_lower in alias_keys or any(sub in k_lower for sub in substrings):
              num = _extract_numeric(v)
              if num is not None:
                return num
          for _, v in obj.items():
            num = _find_numeric_deep(v, alias_keys, substrings)
            if num is not None:
              return num
          return None
        # 列表：逐项递归
        if isinstance(obj, list):
          for item in obj:
            num = _find_numeric_deep(item, alias_keys, substrings)
            if num is not None:
              return num
          return None
        # 基本类型直接尝试转换（仅当无键匹配情况下，不作角/扭矩猜测）
        return None
      except Exception:
        return None

    angle_alias = {
      'angle','position_deg','position','theta','angle_deg','angular_position','pos','deg',
      'mechanical_angle','electrical_angle','encoder_position','encoder_deg','theta_deg','position_degree','angle_degree',
      '角度','角位移','位置','机械角度','电角度','编码器位置','编码器角度'
    }
    torque_alias = {
      'torque','torque_nm','load_torque','current_torque','torque_Nm','tq','load_torque_nm',
      'load_torque_nm','motor_torque','output_torque','torque_value',
      '扭矩','负载扭矩','输出扭矩','电机扭矩','当前扭矩'
    }
    angle = _find_numeric_deep(values, angle_alias, ['angle','position','theta','pos','deg','encoder','角','位移','位置'])
    torque = _find_numeric_deep(values, torque_alias, ['torque','load','nm','tq','扭矩','负载'])

    source = 'node_red' if values else 'database'

    if torque is None:
      try:
        from app.services.data_service import DataService
        hist_torque = DataService.get_measurement_history('start_torque', limit=1)
        if hist_torque and isinstance(hist_torque, list):
          last = hist_torque[0]
          tv = last.get('value') if isinstance(last, dict) else None
          torque = float(tv) if tv is not None else None
      except Exception as e:
        logger.warning(f"回退读取历史扭矩失败: {e}")

    duration = now_ms() - start_time
    meta = {
      'source': source,
      'timestamp': now_ms(),
      'keys': list(values.keys()) if isinstance(values, dict) else []
    }
    log_api_call('/api/data/current','GET',{}, {'angle': angle, 'torque': torque, 'source': source, 'keys': meta['keys']}, duration)
    return jsonify({'angle': angle, 'torque': torque, '_meta': meta})
  except Exception as e:
    logger.error(f"获取当前实时数据失败: {e}")
    error_response, status_code = create_response(success=False, error=str(e), message='获取当前实时数据失败', status_code=500)
    return jsonify(error_response), status_code