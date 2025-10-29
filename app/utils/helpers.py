"""
通用工具函数
"""
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def now_ms() -> int:
    """获取当前时间戳（毫秒）"""
    return int(time.time() * 1000)


def format_timestamp(ts: Optional[int] = None) -> str:
    """格式化时间戳为可读字符串"""
    if ts is None:
        ts = now_ms()
    try:
        return datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, OSError):
        return str(ts)


def normalize_measurement_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """标准化测量数据格式"""
    normalized = {}
    
    for key, item in data.items():
        if isinstance(item, dict):
            normalized[key] = {
                'value': float(item.get('value', 0)),
                'unit': item.get('unit', ''),
                'addr': item.get('addr', ''),
                'timestamp': item.get('timestamp', now_ms())
            }
        else:
            # 简单数值
            normalized[key] = {
                'value': float(item),
                'unit': '',
                'addr': '',
                'timestamp': now_ms()
            }
    
    return normalized


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全的JSON解析"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"JSON解析失败: {e}")
        return default


def safe_json_dumps(obj: Any, default: str = '{}') -> str:
    """安全的JSON序列化"""
    try:
        return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    except (TypeError, ValueError) as e:
        logger.warning(f"JSON序列化失败: {e}")
        return default


def validate_measurement_keys(data: Dict[str, Any], required_keys: List[str]) -> bool:
    """验证测量数据是否包含必需的键"""
    return all(key in data for key in required_keys)


def create_response(success: bool = True, data: Any = None, message: str = '', 
                   error: str = '', status_code: int = 200) -> tuple:
    """创建标准化的API响应"""
    response = {
        'success': success,
        'timestamp': now_ms(),
        'message': message
    }
    
    if success and data is not None:
        response['data'] = data
    elif not success and error:
        response['error'] = error
    
    return response, status_code


def log_api_call(endpoint: str, method: str, params: Dict[str, Any] = None, 
                response_data: Any = None, duration_ms: float = 0):
    """记录API调用日志"""
    log_data = {
        'endpoint': endpoint,
        'method': method,
        'duration_ms': round(duration_ms, 2),
        'timestamp': format_timestamp()
    }
    
    if params:
        log_data['params'] = params
    if response_data:
        log_data['response_size'] = len(str(response_data))
    
    logger.info(f"API调用: {safe_json_dumps(log_data)}")


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """将列表分块"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """合并多个字典"""
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result