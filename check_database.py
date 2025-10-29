#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库中的电机数据
"""

import sqlite3
import json
import os

def check_database():
    """检查数据库中的电机数据"""
    # 尝试多个可能的数据库路径
    possible_paths = [
        'data/app.db',
        'data/database/data.db',
        'data/database/measurements.db',
        'server/data.db'
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ 未找到数据库文件，尝试的路径:")
        for path in possible_paths:
            print(f"  - {path}")
        return
    
    print(f"✓ 找到数据库文件: {db_path}")
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("\n=== 检查数据库表结构 ===")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        for table in tables:
            print(f"表: {table[0]}")
        
        print("\n=== 检查custom_motors表数据 ===")
        try:
            cursor.execute("SELECT * FROM custom_motors")
            motors = cursor.fetchall()
            print(f"电机数量: {len(motors)}")
            
            empty_name_count = 0
            for motor in motors:
                motor_dict = dict(motor)
                name = motor_dict.get('name', '')
                print(f"ID: {motor_dict['id']}, 名称: \"{name}\"")
                
                if not name or name.strip() == '':
                    print("  ⚠️  发现空白名称电机!")
                    empty_name_count += 1
            
            if empty_name_count > 0:
                print(f"\n❌ 发现 {empty_name_count} 个空白名称电机")
                
                # 询问是否删除空白电机
                print("\n=== 清理空白电机 ===")
                cursor.execute("DELETE FROM custom_motors WHERE name IS NULL OR name = '' OR TRIM(name) = ''")
                deleted_count = cursor.rowcount
                conn.commit()
                print(f"✓ 已删除 {deleted_count} 个空白名称电机")
                
                # 重新检查
                cursor.execute("SELECT * FROM custom_motors")
                motors = cursor.fetchall()
                print(f"✓ 清理后电机数量: {len(motors)}")
                
            else:
                print("✓ 没有发现空白名称电机")
                
        except Exception as e:
            print(f"❌ 检查custom_motors表时出错: {e}")
        
        # 检查其他相关表
        print("\n=== 检查其他相关表 ===")
        other_tables = ['measurements', 'hysteresis_data', 'command_history']
        for table_name in other_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"{table_name}: {count} 条记录")
            except Exception as e:
                print(f"{table_name}: 表不存在或出错 - {e}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 数据库操作出错: {e}")

if __name__ == "__main__":
    check_database()