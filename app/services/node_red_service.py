"""
Node-RED代理服务
"""
import logging
import requests
from typing import Dict, Any, Optional
from flask import current_app
from app.utils.helpers import now_ms, safe_json_loads, safe_json_dumps

logger = logging.getLogger(__name__)


class NodeRedService:
    """Node-RED代理服务"""
    
    @staticmethod
    def create_command_log(command: str, params: Optional[Dict[str, Any]] = None) -> int:
        """创建命令日志（pending），返回日志ID"""
        try:
            from app.utils.database import execute_insert_return_id
            query = '''
                INSERT INTO command_logs (command, params, response, status)
                VALUES (?, ?, ?, ?)
            '''
            params_json = safe_json_dumps(params) if params else None
            log_id = execute_insert_return_id(query, [command, params_json, None, 'pending'])
            return int(log_id or 0)
        except Exception as e:
            logger.error(f"创建命令日志失败: {e}")
            return 0
    
    @staticmethod
    def complete_command_log(log_id: int, response: Optional[Dict[str, Any]] = None, success: bool = True) -> None:
        """完成命令日志：更新响应与状态"""
        try:
            from app.utils.database import execute_query
            status = 'success' if success else 'failed'
            query = '''
                UPDATE command_logs
                SET response = ?, status = ?
                WHERE id = ?
            '''
            response_json = safe_json_dumps(response) if response else None
            execute_query(query, [response_json, status, log_id])
        except Exception as e:
            logger.error(f"更新命令日志失败(id={log_id}): {e}")
    
    @staticmethod
    def get_timeout() -> int:
        """获取请求超时时间"""
        return current_app.config.get('NODE_RED_TIMEOUT', 5)
    
    @staticmethod
    def get_base_url() -> str:
        """获取Node-RED基础URL"""
        return current_app.config.get('NODE_RED_BASE_URL', 'http://127.0.0.1:1880')

    # 新增：优先从数据库读取采集/写入完整地址
    @staticmethod
    def get_collection_url() -> str:
        """获取数据采集完整URL（优先系统配置）"""
        try:
            from app.utils.database import execute_query
            row = execute_query(
                'SELECT config_value FROM system_config WHERE config_key = ?',
                ['data_collection_url'],
                fetch_one=True
            )
            url = ''
            if row:
                try:
                    # sqlite3.Row 支持按列名索引
                    url = row['config_value']
                except Exception:
                    # 兜底：将 Row 转为 dict 或按位置索引
                    try:
                        url = dict(row).get('config_value', '')
                    except Exception:
                        url = row[0] if len(row) > 0 else ''
            if url:
                return url.strip()
        except Exception as e:
            logger.warning(f"读取采集URL失败: {e}")
        base_url = NodeRedService.get_base_url()
        return f"{base_url}/get/datas"

    @staticmethod
    def get_write_url() -> str:
        """获取数据写入完整URL（优先系统配置）"""
        try:
            from app.utils.database import execute_query
            row = execute_query(
                'SELECT config_value FROM system_config WHERE config_key = ?',
                ['data_write_url'],
                fetch_one=True
            )
            url = ''
            if row:
                try:
                    url = row['config_value']
                except Exception:
                    try:
                        url = dict(row).get('config_value', '')
                    except Exception:
                        url = row[0] if len(row) > 0 else ''
            if url:
                return url.strip()
        except Exception as e:
            logger.warning(f"读取写入URL失败: {e}")
        base_url = NodeRedService.get_base_url()
        return f"{base_url}/set/data"

    @staticmethod
    def fetch_data_from_node_red() -> Optional[Dict[str, Any]]:
        """从Node-RED获取数据"""
        try:
            timeout = NodeRedService.get_timeout()
            url = NodeRedService.get_collection_url()
            
            logger.info(f"正在从Node-RED获取数据(GET优先): {url}")
            
            def _extract_values(payload: Any) -> Optional[Dict[str, Any]]:
                """兼容多种Node-RED返回结构，提取测量值映射"""
                try:
                    # 情况1：列表（多条消息）
                    if isinstance(payload, list):
                        for item in payload:
                            res = _extract_values(item)
                            if isinstance(res, dict) and res:
                                return res
                        return None
                    # 情况2：非字典直接返回空
                    if not isinstance(payload, dict):
                        return None
                    # 情况3：msg.payload 包装
                    if 'payload' in payload and isinstance(payload['payload'], (dict, list)):
                        res = _extract_values(payload['payload'])
                        if isinstance(res, dict) and res:
                            return res
                    # 情况4：直接包含 values
                    if 'values' in payload and isinstance(payload['values'], dict):
                        return payload['values']
                    # 情况5：data.values 包装
                    data_obj = payload.get('data')
                    if isinstance(data_obj, dict):
                        vals = data_obj.get('values')
                        if isinstance(vals, dict):
                            return vals
                    # 情况6：顶层就是测量键映射（接受数字、字典或字符串）
                    if all(isinstance(v, (dict, int, float, str)) for v in payload.values()):
                        return payload
                    return None
                except Exception:
                    return None
            
            # 尝试 GET 请求
            response = requests.get(
                url,
                timeout=timeout,
                headers={'Accept': 'application/json'}
            )
            
            if response.status_code == 200:
                payload = response.json()
                values = _extract_values(payload)
                if isinstance(values, dict) and values:
                    logger.info(f"成功从Node-RED(GET)获取数据，键数量: {len(values)}")
                    return values
                else:
                    logger.warning("Node-RED返回格式不含values，尝试POST方式")
            else:
                logger.info(f"GET方式未成功(status={response.status_code})，尝试POST")
            
            # 回退：POST 空JSON体
            logger.info(f"正在从Node-RED获取数据(POST回退): {url}")
            response = requests.post(
                url,
                json={},
                timeout=timeout,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            payload = response.json()
            values = _extract_values(payload)
            if isinstance(values, dict) and values:
                logger.info(f"成功从Node-RED(POST)获取数据，键数量: {len(values)}")
                return values
            else:
                logger.error("Node-RED返回数据不含测量值映射(values)，放弃")
                return None
            
        except requests.exceptions.Timeout:
            logger.warning(f"Node-RED请求超时 (> {NodeRedService.get_timeout()}s)")
            return None
        except requests.exceptions.ConnectionError:
            logger.warning("无法连接到Node-RED服务")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"Node-RED HTTP错误: {e}")
            return None
        except Exception as e:
            logger.error(f"从Node-RED获取数据失败: {e}")
            return None

    @staticmethod
    def send_command_to_node_red(command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """向Node-RED发送命令"""
        try:
            timeout = NodeRedService.get_timeout()
            
            # 优先使用配置中的完整写入地址
            url = NodeRedService.get_write_url()
            
            # 准备请求数据
            request_data = {
                'command': command,
                'timestamp': now_ms()
            }
            
            if params:
                request_data.update(params)
            
            logger.info(f"正在向Node-RED发送命令: {command} -> {url}")
            
            # 发送POST请求
            response = requests.post(
                url,
                json=request_data,
                timeout=timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            
            logger.info(f"命令发送成功: {command}")
            
            return {
                'success': True,
                'command': command,
                'response': result,
                'timestamp': now_ms()
            }
            
        except requests.exceptions.Timeout:
            error_msg = f"Node-RED命令请求超时 (> {timeout}s): {command}"
            logger.warning(error_msg)
            return {
                'success': False,
                'command': command,
                'error': 'timeout',
                'message': error_msg,
                'timestamp': now_ms()
            }
        except requests.exceptions.ConnectionError:
            error_msg = f"无法连接到Node-RED服务: {command}"
            logger.warning(error_msg)
            return {
                'success': False,
                'command': command,
                'error': 'connection_error',
                'message': error_msg,
                'timestamp': now_ms()
            }
        except requests.exceptions.HTTPError as e:
            error_msg = f"Node-RED HTTP错误: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'command': command,
                'error': 'http_error',
                'message': error_msg,
                'timestamp': now_ms()
            }
        except Exception as e:
            error_msg = f"向Node-RED发送命令失败: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'command': command,
                'error': 'unknown_error',
                'message': error_msg,
                'timestamp': now_ms()
            }
    
    @staticmethod
    def test_node_red_connection() -> Dict[str, Any]:
        """测试Node-RED连接"""
        try:
            timeout = NodeRedService.get_timeout()
            base_url = NodeRedService.get_base_url()
            collection_url = NodeRedService.get_collection_url()
            write_url = NodeRedService.get_write_url()
            
            # 优先测试已配置的完整地址
            test_urls = [
                collection_url,
                write_url,
                f"{base_url}/health",
                f"{base_url}/",
                f"{base_url}/get/datas"
            ]
            
            for url in test_urls:
                try:
                    response = requests.get(url, timeout=timeout)
                    if response.status_code < 500:  # 任何非服务器错误都算连接成功
                        return {
                            'success': True,
                            'url': url,
                            'status_code': response.status_code,
                            'message': 'Node-RED连接正常',
                            'timestamp': now_ms()
                        }
                except:
                    continue
            
            return {
                'success': False,
                'error': 'connection_failed',
                'message': 'Node-RED连接失败',
                'base_url': base_url,
                'timestamp': now_ms()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': 'test_error',
                'message': f'Node-RED连接测试失败: {e}',
                'timestamp': now_ms()
            }
    
    @staticmethod
    def log_command(command: str, params: Optional[Dict[str, Any]] = None, 
                   response: Optional[Dict[str, Any]] = None, status: str = 'pending'):
        """记录命令日志（兼容旧接口，不返回ID）"""
        try:
            from app.utils.database import execute_query
            query = '''
                INSERT INTO command_logs (command, params, response, status)
                VALUES (?, ?, ?, ?)
            '''
            params_json = safe_json_dumps(params) if params else None
            response_json = safe_json_dumps(response) if response else None
            execute_query(query, [command, params_json, response_json, status])
        except Exception as e:
            logger.error(f"记录命令日志失败: {e}")

    @staticmethod
    def get_command_history(limit: int = 50) -> list:
        """获取命令历史"""
        try:
            from app.utils.database import execute_query
            
            query = '''
                SELECT command, params, response, status, created_at
                FROM command_logs
                ORDER BY created_at DESC
                LIMIT ?
            '''
            
            rows = execute_query(query, [limit], fetch_all=True)
            
            result = []
            for row in rows:
                result.append({
                    'command': row['command'],
                    'params': safe_json_loads(row['params']),
                    'response': safe_json_loads(row['response']),
                    'status': row['status'],
                    'created_at': row['created_at']
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取命令历史失败: {e}")
            return []