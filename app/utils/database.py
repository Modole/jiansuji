"""
数据库工具模块
"""
import sqlite3
import logging
from flask import g, current_app
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def get_db():
    """获取数据库连接"""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE_PATH'])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """关闭数据库连接"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


@contextmanager
def get_db_connection():
    """数据库连接上下文管理器"""
    conn = sqlite3.connect(current_app.config['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"数据库操作错误: {e}")
        raise
    else:
        conn.commit()
    finally:
        conn.close()


def init_db():
    """初始化数据库"""
    try:
        with get_db_connection() as conn:
            conn.executescript('''
                -- 测量数据表
                CREATE TABLE IF NOT EXISTS measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    addr TEXT,
                    value REAL,
                    unit TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_measurements_key_ts ON measurements(key, ts);
                CREATE INDEX IF NOT EXISTS idx_measurements_created_at ON measurements(created_at);
                
                -- 滞回曲线数据表
                CREATE TABLE IF NOT EXISTS hysteresis_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    angle REAL NOT NULL,
                    torque REAL NOT NULL,
                    curve_type TEXT DEFAULT 'hysteresis',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 创建索引（注意：curve_type索引在迁移检查后创建）
                CREATE INDEX IF NOT EXISTS idx_hysteresis_ts ON hysteresis_points(ts);
                CREATE INDEX IF NOT EXISTS idx_hysteresis_created_at ON hysteresis_points(created_at);
                
                -- 命令日志表
                CREATE TABLE IF NOT EXISTS command_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    params TEXT,
                    response TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_command_logs_created_at ON command_logs(created_at);
                CREATE INDEX IF NOT EXISTS idx_command_logs_status ON command_logs(status);
                
                -- 自定义电机配置表
                CREATE TABLE IF NOT EXISTS custom_motors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    rated_voltage REAL DEFAULT 0,
                    rated_current REAL DEFAULT 0,
                    max_torque REAL DEFAULT 0,
                    rated_speed REAL DEFAULT 0,
                    pole_pairs INTEGER DEFAULT 0,
                    inertia REAL DEFAULT 0,
                    encoder_resolution INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_custom_motors_name ON custom_motors(name);
                CREATE INDEX IF NOT EXISTS idx_custom_motors_created_at ON custom_motors(created_at);
                
                -- 系统配置表
                CREATE TABLE IF NOT EXISTS system_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT NOT NULL UNIQUE,
                    config_value TEXT,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_config(config_key);
                
                -- 插入默认的连接配置
                INSERT OR IGNORE INTO system_config (config_key, config_value, description) 
                VALUES 
                    ('data_collection_url', '', '数据采集地址'),
                    ('data_write_url', '', '数据写入地址');
            ''')
            
            # 迁移：如果旧库缺少 curve_type 字段，则补充该列
            try:
                cur = conn.execute("PRAGMA table_info(hysteresis_points)")
                cols = [row['name'] for row in cur.fetchall()]
                if 'curve_type' not in cols:
                    conn.execute("ALTER TABLE hysteresis_points ADD COLUMN curve_type TEXT DEFAULT 'hysteresis'")
                    logger.info("已为 hysteresis_points 添加 curve_type 字段")
                
                # 统一创建（或确保存在）基于 curve_type 与 ts 的复合索引
                conn.execute("CREATE INDEX IF NOT EXISTS idx_hysteresis_curve_type_ts ON hysteresis_points(curve_type, ts)")
                logger.info("已确保存在 idx_hysteresis_curve_type_ts 索引")
            except Exception as mig_err:
                # 不影响整体初始化流程，但记录日志，便于排查
                logger.warning(f"检查/迁移 hysteresis_points.curve_type 失败: {mig_err}")
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise


def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """执行数据库查询"""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(query, params or [])
            
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            else:
                return cursor.rowcount
    except Exception as e:
        logger.error(f"查询执行失败: {query}, 参数: {params}, 错误: {e}")
        raise


def execute_many(query, params_list):
    """批量执行数据库操作"""
    try:
        with get_db_connection() as conn:
            cursor = conn.executemany(query, params_list)
            return cursor.rowcount
    except Exception as e:
        logger.error(f"批量操作失败: {query}, 错误: {e}")
        raise


def execute_insert_return_id(query, params=None):
    """执行插入并返回生成的ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(query, params or [])
            # lastrowid 在成功插入时返回自增主键值
            return int(cursor.lastrowid or 0)
    except Exception as e:
        logger.error(f"插入执行失败: {query}, 参数: {params}, 错误: {e}")
        raise