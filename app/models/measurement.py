"""
测量数据模型
"""
import logging
from typing import Dict, List, Optional, Any
from app.utils.database import execute_query, execute_many
from app.utils.helpers import now_ms, normalize_measurement_data

logger = logging.getLogger(__name__)


class MeasurementModel:
    """测量数据模型"""
    
    @staticmethod
    def save_measurements(data: Dict[str, Any], timestamp: Optional[int] = None) -> int:
        """保存测量数据"""
        if not data:
            return 0
        
        ts = timestamp or now_ms()
        normalized_data = normalize_measurement_data(data)
        
        # 准备批量插入数据
        insert_data = []
        for key, item in normalized_data.items():
            insert_data.append((
                ts,
                key,
                item.get('addr', ''),
                item.get('value', 0),
                item.get('unit', '')
            ))
        
        query = '''
            INSERT INTO measurements (ts, key, addr, value, unit)
            VALUES (?, ?, ?, ?, ?)
        '''
        
        try:
            return execute_many(query, insert_data)
        except Exception as e:
            logger.error(f"保存测量数据失败: {e}")
            raise
    
    @staticmethod
    def get_latest_measurements(keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """获取最新的测量数据"""
        if keys:
            placeholders = ','.join(['?' for _ in keys])
            query = f'''
                SELECT key, value, unit, addr, ts
                FROM measurements
                WHERE key IN ({placeholders})
                AND ts = (
                    SELECT MAX(ts) FROM measurements m2 
                    WHERE m2.key = measurements.key
                )
                ORDER BY key
            '''
            params = keys
        else:
            query = '''
                SELECT key, value, unit, addr, ts
                FROM measurements
                WHERE ts = (
                    SELECT MAX(ts) FROM measurements m2 
                    WHERE m2.key = measurements.key
                )
                ORDER BY key
            '''
            params = []
        
        try:
            rows = execute_query(query, params, fetch_all=True)
            result = {}
            
            for row in rows:
                result[row['key']] = {
                    'value': row['value'],
                    'unit': row['unit'],
                    'addr': row['addr'],
                    'timestamp': row['ts']
                }
            
            return result
        except Exception as e:
            logger.error(f"获取最新测量数据失败: {e}")
            return {}
    
    @staticmethod
    def get_measurements_by_timerange(start_ts: int, end_ts: int, 
                                    keys: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """根据时间范围获取测量数据"""
        base_query = '''
            SELECT key, value, unit, addr, ts, created_at
            FROM measurements
            WHERE ts BETWEEN ? AND ?
        '''
        params = [start_ts, end_ts]
        
        if keys:
            placeholders = ','.join(['?' for _ in keys])
            base_query += f' AND key IN ({placeholders})'
            params.extend(keys)
        
        base_query += ' ORDER BY ts DESC, key'
        
        try:
            rows = execute_query(base_query, params, fetch_all=True)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"根据时间范围获取测量数据失败: {e}")
            return []
    
    @staticmethod
    def get_measurement_history(key: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取指定键的历史数据"""
        query = '''
            SELECT value, unit, addr, ts, created_at
            FROM measurements
            WHERE key = ?
            ORDER BY ts DESC
            LIMIT ?
        '''
        
        try:
            rows = execute_query(query, [key, limit], fetch_all=True)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取测量历史数据失败: {e}")
            return []
    
    @staticmethod
    def delete_old_measurements(days: int = 30) -> int:
        """删除旧的测量数据"""
        cutoff_ts = now_ms() - (days * 24 * 60 * 60 * 1000)
        query = 'DELETE FROM measurements WHERE ts < ?'
        
        try:
            return execute_query(query, [cutoff_ts])
        except Exception as e:
            logger.error(f"删除旧测量数据失败: {e}")
            return 0
    
    @staticmethod
    def get_measurement_stats() -> Dict[str, Any]:
        """获取测量数据统计信息"""
        queries = {
            'total_count': 'SELECT COUNT(*) as count FROM measurements',
            'unique_keys': 'SELECT COUNT(DISTINCT key) as count FROM measurements',
            'latest_timestamp': 'SELECT MAX(ts) as ts FROM measurements',
            'oldest_timestamp': 'SELECT MIN(ts) as ts FROM measurements'
        }
        
        stats = {}
        for stat_name, query in queries.items():
            try:
                row = execute_query(query, fetch_one=True)
                if row:
                    stats[stat_name] = row[0] if len(row) == 1 else dict(row)
            except Exception as e:
                logger.error(f"获取统计信息失败 {stat_name}: {e}")
                stats[stat_name] = None
        
        return stats