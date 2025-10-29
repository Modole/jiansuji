"""
滞回曲线数据模型
"""
import logging
import math
from typing import List, Dict, Any, Optional, Tuple
from app.utils.database import execute_query, execute_many
from app.utils.helpers import now_ms

logger = logging.getLogger(__name__)


class HysteresisModel:
    """滞回曲线数据模型"""
    
    # 曲线类型常量
    CURVE_TYPE_FORWARD = 'forward'      # 正向曲线
    CURVE_TYPE_REVERSE = 'reverse'      # 反向曲线
    CURVE_TYPE_HYSTERESIS = 'hysteresis'  # 滞回曲线
    
    @staticmethod
    def save_hysteresis_points(points: List[Dict[str, float]], 
                             curve_type: str = 'hysteresis',
                             timestamp: Optional[int] = None) -> int:
        """保存滞回曲线数据点"""
        if not points:
            return 0
        
        ts = timestamp or now_ms()
        
        # 准备批量插入数据
        insert_data = []
        for point in points:
            if 'angle' in point and 'torque' in point:
                insert_data.append((
                    ts,
                    float(point['angle']),
                    float(point['torque']),
                    curve_type
                ))
        
        if not insert_data:
            logger.warning("没有有效的滞回曲线数据点")
            return 0
        
        query = '''
            INSERT INTO hysteresis_points (ts, angle, torque, curve_type)
            VALUES (?, ?, ?, ?)
        '''
        
        try:
            return execute_many(query, insert_data)
        except Exception as e:
            logger.error(f"保存滞回曲线数据失败: {e}")
            raise
    
    @staticmethod
    def get_latest_hysteresis_points(curve_type: Optional[str] = None) -> List[Dict[str, float]]:
        """获取最新的滞回曲线数据"""
        if curve_type:
            query = '''
                SELECT angle, torque, curve_type
                FROM hysteresis_points
                WHERE ts = (SELECT MAX(ts) FROM hysteresis_points WHERE curve_type = ?)
                AND curve_type = ?
                ORDER BY id
            '''
            params = [curve_type, curve_type]
        else:
            query = '''
                SELECT angle, torque, curve_type
                FROM hysteresis_points
                WHERE ts = (SELECT MAX(ts) FROM hysteresis_points)
                ORDER BY id
            '''
            params = []
        
        try:
            rows = execute_query(query, params, fetch_all=True)
            return [{'angle': row['angle'], 'torque': row['torque'], 'curve_type': dict(row).get('curve_type', 'hysteresis')} for row in rows]
        except Exception as e:
            logger.error(f"获取最新滞回曲线数据失败: {e}")
            return []
    
    @staticmethod
    def get_hysteresis_by_timestamp(timestamp: int, curve_type: Optional[str] = None) -> List[Dict[str, float]]:
        """根据时间戳获取滞回曲线数据"""
        if curve_type:
            query = '''
                SELECT angle, torque, curve_type
                FROM hysteresis_points
                WHERE ts = ? AND curve_type = ?
                ORDER BY id
            '''
            params = [timestamp, curve_type]
        else:
            query = '''
                SELECT angle, torque, curve_type
                FROM hysteresis_points
                WHERE ts = ?
                ORDER BY id
            '''
            params = [timestamp]
        
        try:
            rows = execute_query(query, params, fetch_all=True)
            return [{'angle': row['angle'], 'torque': row['torque'], 'curve_type': dict(row).get('curve_type', 'hysteresis')} for row in rows]
        except Exception as e:
            logger.error(f"根据时间戳获取滞回曲线数据失败: {e}")
            return []
    
    @staticmethod
    def get_hysteresis_timestamps(limit: int = 10) -> List[int]:
        """获取滞回曲线数据的时间戳列表"""
        query = '''
            SELECT DISTINCT ts
            FROM hysteresis_points
            ORDER BY ts DESC
            LIMIT ?
        '''
        
        try:
            rows = execute_query(query, [limit], fetch_all=True)
            return [row['ts'] for row in rows]
        except Exception as e:
            logger.error(f"获取滞回曲线时间戳失败: {e}")
            return []
    
    @staticmethod
    def separate_curve_data(raw_data: List[Dict[str, float]]) -> Dict[str, List[Dict[str, float]]]:
        """
        将原始数据分离为正向、反向和滞回曲线
        基于角位移的变化方向来判断曲线类型
        """
        if not raw_data:
            return {
                HysteresisModel.CURVE_TYPE_FORWARD: [],
                HysteresisModel.CURVE_TYPE_REVERSE: [],
                HysteresisModel.CURVE_TYPE_HYSTERESIS: []
            }
        
        forward_points = []
        reverse_points = []
        hysteresis_points = []
        
        # 按时间排序
        sorted_data = sorted(raw_data, key=lambda x: x.get('timestamp', 0))
        
        # 分析角位移变化趋势
        for i, point in enumerate(sorted_data):
            if i == 0:
                # 第一个点默认为正向
                forward_points.append(point)
                continue
            
            prev_angle = sorted_data[i-1]['angle']
            curr_angle = point['angle']
            
            # 判断角位移变化方向
            if curr_angle > prev_angle:
                # 角位移增加 - 正向
                forward_points.append(point)
            elif curr_angle < prev_angle:
                # 角位移减少 - 反向
                reverse_points.append(point)
            else:
                # 角位移不变 - 归入滞回
                hysteresis_points.append(point)
        
        # 生成完整的滞回曲线（包含正向和反向的所有点）
        hysteresis_points = sorted_data.copy()
        
        return {
            HysteresisModel.CURVE_TYPE_FORWARD: forward_points,
            HysteresisModel.CURVE_TYPE_REVERSE: reverse_points,
            HysteresisModel.CURVE_TYPE_HYSTERESIS: hysteresis_points
        }
    
    @staticmethod
    def save_separated_curve_data(raw_data: List[Dict[str, float]], 
                                timestamp: Optional[int] = None) -> Dict[str, int]:
        """
        保存分离后的三种曲线数据
        返回每种曲线类型保存的数据点数量
        """
        separated_data = HysteresisModel.separate_curve_data(raw_data)
        result = {}
        
        for curve_type, points in separated_data.items():
            if points:
                count = HysteresisModel.save_hysteresis_points(points, curve_type, timestamp)
                result[curve_type] = count
            else:
                result[curve_type] = 0
        
        return result
    
    @staticmethod
    def delete_old_hysteresis_data(days: int = 30) -> int:
        """删除旧的滞回曲线数据"""
        cutoff_ts = now_ms() - (days * 24 * 60 * 60 * 1000)
        query = 'DELETE FROM hysteresis_points WHERE ts < ?'
        
        try:
            return execute_query(query, [cutoff_ts])
        except Exception as e:
            logger.error(f"删除旧滞回曲线数据失败: {e}")
            return 0
    
    @staticmethod
    def generate_mock_hysteresis(count: int = 240, period: float = 10.0, 
                               backlash: float = 0.6, stiffness: float = 0.8) -> List[Dict[str, float]]:
        """生成模拟滞回曲线数据（闭合回线）"""
        # 将总点数分为正向与反向两个阶段，形成闭合环
        half = max(2, count // 2)
        points: List[Dict[str, float]] = []

        # 正向扫描：角度从 -period/2 到 +period/2
        for i in range(half):
            u = i / (half - 1)
            angle = (-period / 2.0) + u * period
            base_torque = angle * stiffness
            # 正向时施加负的滞回偏移
            hysteresis = -backlash * (1.0 - math.cos(math.pi * u))
            noise = 0.05 * math.sin(i * 0.2) * stiffness
            torque = base_torque + hysteresis + noise
            points.append({'angle': round(angle, 3), 'torque': round(torque, 3)})

        # 反向扫描：角度从 +period/2 回到 -period/2
        for i in range(half):
            u = i / (half - 1)
            angle = (period / 2.0) - u * period
            base_torque = angle * stiffness
            # 反向时施加正的滞回偏移
            hysteresis = +backlash * (1.0 - math.cos(math.pi * u))
            noise = 0.05 * math.sin((i + half) * 0.2) * stiffness
            torque = base_torque + hysteresis + noise
            points.append({'angle': round(angle, 3), 'torque': round(torque, 3)})

        return points
    
    @staticmethod
    def analyze_hysteresis_curve(points: List[Dict[str, float]]) -> Dict[str, Any]:
        """分析滞回曲线特性"""
        if not points:
            return {}
        
        angles = [p['angle'] for p in points]
        torques = [p['torque'] for p in points]
        
        analysis = {
            'point_count': len(points),
            'angle_range': {
                'min': min(angles),
                'max': max(angles),
                'span': max(angles) - min(angles)
            },
            'torque_range': {
                'min': min(torques),
                'max': max(torques),
                'span': max(torques) - min(torques)
            }
        }
        
        # 计算滞回面积（简单梯形积分）
        try:
            area = 0
            for i in range(1, len(points)):
                area += (angles[i] - angles[i-1]) * (torques[i] + torques[i-1]) / 2
            analysis['hysteresis_area'] = abs(area)
        except Exception as e:
            logger.warning(f"计算滞回面积失败: {e}")
            analysis['hysteresis_area'] = 0
        
        # 估算刚度（线性拟合斜率）
        try:
            n = len(points)
            sum_xy = sum(angles[i] * torques[i] for i in range(n))
            sum_x = sum(angles)
            sum_y = sum(torques)
            sum_x2 = sum(a * a for a in angles)
            
            if n * sum_x2 - sum_x * sum_x != 0:
                stiffness = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                analysis['estimated_stiffness'] = stiffness
        except Exception as e:
            logger.warning(f"估算刚度失败: {e}")
            analysis['estimated_stiffness'] = 0
        
        return analysis