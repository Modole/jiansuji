"""
数据处理服务
"""
import logging
from typing import Dict, List, Any, Optional
from app.models.measurement import MeasurementModel
from app.models.hysteresis import HysteresisModel
from app.utils.helpers import now_ms, normalize_measurement_data
from flask import current_app

logger = logging.getLogger(__name__)


class DataService:
    """数据处理服务"""
    
    # 静态页面测量键
    STATIC_KEYS = [
        'unidirectional_error', 'lost_motion', 
        'backlash', 'torsional_stiffness'
    ]
    
    # 动态页面测量键
    DYNAMIC_KEYS = [
        'start_torque', 'no_load_accuracy', 
        'variable_load_accuracy', 'peak_load_accuracy',
        'transmission_efficiency', 'noise_level'
    ]
    
    ALL_KEYS = STATIC_KEYS + DYNAMIC_KEYS
    
    @staticmethod
    def get_current_measurements(keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """获取当前测量数据"""
        try:
            # 如果没有指定键，使用所有键
            if keys is None:
                keys = DataService.ALL_KEYS
            
            # 从数据库获取最新数据
            latest_data = MeasurementModel.get_latest_measurements(keys)
            
            # 如果数据库中没有数据，返回默认值
            if not latest_data:
                logger.info("数据库中没有测量数据，返回默认值")
                return DataService._get_default_measurements(keys)
            
            # 检查是否有缺失的键，用默认值补充
            result = {}
            for key in keys:
                if key in latest_data:
                    result[key] = latest_data[key]
                else:
                    result[key] = DataService._get_default_value(key)
            
            return result
            
        except Exception as e:
            logger.error(f"获取当前测量数据失败: {e}")
            return DataService._get_default_measurements(keys or DataService.ALL_KEYS)
    
    @staticmethod
    def save_measurement_data(data: Dict[str, Any], timestamp: Optional[int] = None) -> bool:
        """保存测量数据"""
        try:
            if not data:
                logger.warning("没有数据需要保存")
                return False
            
            # 标准化数据格式
            normalized_data = normalize_measurement_data(data)
            
            # 保存到数据库
            saved_count = MeasurementModel.save_measurements(normalized_data, timestamp)
            
            if saved_count > 0:
                logger.info(f"成功保存 {saved_count} 条测量数据")
                return True
            else:
                logger.warning("没有数据被保存")
                return False
                
        except Exception as e:
            logger.error(f"保存测量数据失败: {e}")
            return False
    
    @staticmethod
    def get_measurement_history(key: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取测量历史数据"""
        try:
            return MeasurementModel.get_measurement_history(key, limit)
        except Exception as e:
            logger.error(f"获取测量历史数据失败: {e}")
            return []
    
    @staticmethod
    def get_hysteresis_curve_data(curve_type: Optional[str] = None) -> List[Dict[str, float]]:
        """获取滞回曲线数据"""
        try:
            # 尝试从数据库获取最新的滞回曲线数据
            points = HysteresisModel.get_latest_hysteresis_points(curve_type)
            
            # 检查数据是否形成闭合回线：角度序列是否既有递增也有递减
            def _has_loop(ps: List[Dict[str, float]]) -> bool:
                if not ps or len(ps) < 3:
                    return False
                inc = any(ps[i]['angle'] > ps[i-1]['angle'] for i in range(1, len(ps)))
                dec = any(ps[i]['angle'] < ps[i-1]['angle'] for i in range(1, len(ps)))
                return inc and dec

            if not points:
                logger.info("滞回曲线数据为空，返回空集")
                return []
            else:
                # 不闭合时也返回现有点，便于前端绘制
                if not _has_loop(points):
                    logger.info("滞回曲线数据不闭合，仍返回现有点以便前端显示")

            return points
        except Exception as e:
            logger.error(f"获取滞回曲线数据失败: {e}")
            # 异常时：直接返回空集，不生成模拟数据
            return []
    
    @staticmethod
    def save_hysteresis_data(points: List[Dict[str, float]], 
                           curve_type: str = 'hysteresis',
                           timestamp: Optional[int] = None) -> bool:
        """保存滞回曲线数据"""
        try:
            if not points:
                logger.warning("没有滞回曲线数据需要保存")
                return False
            
            saved_count = HysteresisModel.save_hysteresis_points(points, curve_type, timestamp)
            
            if saved_count > 0:
                logger.info(f"成功保存 {saved_count} 个滞回曲线数据点 (类型: {curve_type})")
                return True
            else:
                logger.warning("没有滞回曲线数据被保存")
                return False
                
        except Exception as e:
            logger.error(f"保存滞回曲线数据失败: {e}")
            return False
    
    @staticmethod
    def save_separated_hysteresis_data(raw_data: List[Dict[str, float]], 
                                     timestamp: Optional[int] = None) -> Dict[str, int]:
        """
        保存分离后的三种曲线数据
        返回每种曲线类型保存的数据点数量
        """
        try:
            return HysteresisModel.save_separated_curve_data(raw_data, timestamp)
        except Exception as e:
            logger.error(f"保存分离的滞回曲线数据失败: {e}")
            return {
                HysteresisModel.CURVE_TYPE_FORWARD: 0,
                HysteresisModel.CURVE_TYPE_REVERSE: 0,
                HysteresisModel.CURVE_TYPE_HYSTERESIS: 0
            }
    
    @staticmethod
    def analyze_hysteresis_curve(points: Optional[List[Dict[str, float]]] = None) -> Dict[str, Any]:
        """分析滞回曲线特性"""
        try:
            if points is None:
                points = DataService.get_hysteresis_curve_data()
            
            return HysteresisModel.analyze_hysteresis_curve(points)
            
        except Exception as e:
            logger.error(f"分析滞回曲线失败: {e}")
            return {}
    
    @staticmethod
    def get_data_statistics() -> Dict[str, Any]:
        """获取数据统计信息"""
        try:
            measurement_stats = MeasurementModel.get_measurement_stats()
            hysteresis_timestamps = HysteresisModel.get_hysteresis_timestamps(5)
            
            return {
                'measurements': measurement_stats,
                'hysteresis': {
                    'recent_timestamps': hysteresis_timestamps,
                    'count': len(hysteresis_timestamps)
                },
                'timestamp': now_ms()
            }
            
        except Exception as e:
            logger.error(f"获取数据统计信息失败: {e}")
            return {'error': str(e), 'timestamp': now_ms()}
    
    @staticmethod
    def _get_default_measurements(keys: List[str]) -> Dict[str, Any]:
        """获取默认测量数据"""
        result = {}
        for key in keys:
            result[key] = DataService._get_default_value(key)
        return result
    
    @staticmethod
    def _get_default_value(key: str) -> Dict[str, Any]:
        """获取单个键的默认值"""
        # 根据不同的测量类型返回合理的默认值
        default_values = {
            'unidirectional_error': {'value': 0.0, 'unit': 'arcmin', 'addr': '', 'timestamp': now_ms()},
            'lost_motion': {'value': 0.0, 'unit': 'arcmin', 'addr': '', 'timestamp': now_ms()},
            'backlash': {'value': 0.0, 'unit': 'arcmin', 'addr': '', 'timestamp': now_ms()},
            'torsional_stiffness': {'value': 0.0, 'unit': 'Nm/arcmin', 'addr': '', 'timestamp': now_ms()},
            'start_torque': {'value': 0.0, 'unit': 'Nm', 'addr': '', 'timestamp': now_ms()},
            'no_load_accuracy': {'value': 0.0, 'unit': 'arcmin', 'addr': '', 'timestamp': now_ms()},
            'variable_load_accuracy': {'value': 0.0, 'unit': 'arcmin', 'addr': '', 'timestamp': now_ms()},
            'peak_load_accuracy': {'value': 0.0, 'unit': 'arcmin', 'addr': '', 'timestamp': now_ms()},
            'transmission_efficiency': {'value': 0.0, 'unit': '%', 'addr': '', 'timestamp': now_ms()},
            'noise_level': {'value': 0.0, 'unit': 'dB', 'addr': '', 'timestamp': now_ms()}
        }
        
        return default_values.get(key, {
            'value': 0.0, 
            'unit': '', 
            'addr': '', 
            'timestamp': now_ms()
        })