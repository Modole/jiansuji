# API接口文档

## 概述

本文档定义了谐波减速机测试系统的API接口规范，包括数据采集（实时数据获取）和数据写入（PLC电机配置）两个核心API。

## 一、数据采集API

### 1.1 接口信息
- **接口名称**: 实时数据采集
- **接口地址**: `/api/data/collect`
- **请求方法**: `POST`
- **功能描述**: 获取谐波减速机测试系统的实时测量数据

### 1.2 请求参数
```json
{
  "keys": ["unidirectional_error", "lost_motion", "backlash", "torsional_stiffness"],
  "timestamp": 1704067200000
}
```

**参数说明**:
- `keys` (可选): 指定需要获取的测量项键值列表，如不提供则返回所有数据
- `timestamp` (可选): 客户端时间戳，用于数据同步

### 1.3 响应格式
```json
{
  "success": true,
  "timestamp": 1704067200000,
  "message": "数据获取成功",
  "data": {
    "values": {
      "unidirectional_error": {
        "addr": "D1001",
        "value": 0.03,
        "unit": "arcmin",
        "timestamp": 1704067200000
      },
      "lost_motion": {
        "addr": "D1002", 
        "value": 0.02,
        "unit": "arcmin",
        "timestamp": 1704067200000
      },
      "backlash": {
        "addr": "D1003",
        "value": 0.01,
        "unit": "arcmin", 
        "timestamp": 1704067200000
      },
      "torsional_stiffness": {
        "addr": "D1004",
        "value": 12.3,
        "unit": "N·m/deg",
        "timestamp": 1704067200000
      },
      "start_torque": {
        "addr": "D2001",
        "value": 0.45,
        "unit": "N·m",
        "timestamp": 1704067200000
      },
      "no_load_accuracy": {
        "addr": "D2002",
        "value": 0.05,
        "unit": "arcmin",
        "timestamp": 1704067200000
      },
      "variable_load_accuracy": {
        "addr": "D2003",
        "value": 0.08,
        "unit": "arcmin",
        "load_level": 50,
        "timestamp": 1704067200000
      },
      "peak_load_accuracy": {
        "addr": "D2004",
        "value": 0.09,
        "unit": "arcmin",
        "timestamp": 1704067200000
      },
      "transmission_efficiency": {
        "addr": "D2005",
        "value": 92.1,
        "unit": "%",
        "timestamp": 1704067200000
      },
      "noise_level": {
        "addr": "D2006",
        "value": 62.4,
        "unit": "dB(A)",
        "timestamp": 1704067200000
      }
    }
  }
}
```

### 1.4 测量项说明

#### 静态系统测量项
- `unidirectional_error`: 单向定位误差 (arcmin)
- `lost_motion`: 失动量 (arcmin)  
- `backlash`: 回程间隙 (arcmin)
- `torsional_stiffness`: 扭转刚度 (N·m/deg)

#### 动态系统测量项
- `start_torque`: 启动转矩 (N·m)
- `no_load_accuracy`: 空载传动精度 (arcmin)
- `variable_load_accuracy`: 变载荷传动精度 (arcmin)
- `peak_load_accuracy`: 峰值载荷传动精度 (arcmin)
- `transmission_efficiency`: 传动效率 (%)
- `noise_level`: 噪声水平 (dB(A))

### 1.5 错误响应
```json
{
  "success": false,
  "timestamp": 1704067200000,
  "error": "连接超时",
  "message": "无法连接到数据采集设备"
}
```

## 二、数据写入API

### 2.1 接口信息
- **接口名称**: PLC电机配置写入
- **接口地址**: `/api/data/write`
- **请求方法**: `POST`
- **功能描述**: 向PLC写入电机相关配置参数

### 2.2 请求参数
```json
{
  "motor_config": {
    "model": "Custom Motor",
    "rated_voltage": 48,
    "rated_current": 5.0,
    "max_torque_nm": 2.5,
    "rated_speed_rpm": 3000,
    "pole_pairs": 4,
    "inertia_kgm2": 0.000015,
    "encoder_resolution": 2048
  },
  "test_config": {
    "test_type": "variable_load_accuracy",
    "load_level": 50,
    "speed_rpm": 600,
    "duration_seconds": 300
  },
  "addresses": {
    "motor_model": "D3001",
    "rated_voltage": "D3002", 
    "rated_current": "D3003",
    "max_torque": "D3004",
    "rated_speed": "D3005",
    "pole_pairs": "D3006",
    "inertia": "D3007",
    "encoder_res": "D3008",
    "test_type": "D3101",
    "load_level": "D3102",
    "test_speed": "D3103",
    "test_duration": "D3104"
  }
}
```

**参数说明**:
- `motor_config`: 电机配置参数
  - `model`: 电机型号
  - `rated_voltage`: 额定电压 (V)
  - `rated_current`: 额定电流 (A)
  - `max_torque_nm`: 最大转矩 (N·m)
  - `rated_speed_rpm`: 额定转速 (rpm)
  - `pole_pairs`: 极对数
  - `inertia_kgm2`: 转动惯量 (kg·m²)
  - `encoder_resolution`: 编码器分辨率
- `test_config`: 测试配置参数
  - `test_type`: 测试类型
  - `load_level`: 载荷等级 (0-100)
  - `speed_rpm`: 测试转速 (rpm)
  - `duration_seconds`: 测试持续时间 (秒)
- `addresses`: PLC地址映射 (可选，用于指定写入地址)

### 2.3 响应格式
```json
{
  "success": true,
  "timestamp": 1704067200000,
  "message": "配置写入成功",
  "data": {
    "written_parameters": 12,
    "failed_parameters": 0,
    "write_results": {
      "motor_model": {"addr": "D3001", "status": "success"},
      "rated_voltage": {"addr": "D3002", "status": "success"},
      "rated_current": {"addr": "D3003", "status": "success"},
      "max_torque": {"addr": "D3004", "status": "success"},
      "rated_speed": {"addr": "D3005", "status": "success"},
      "pole_pairs": {"addr": "D3006", "status": "success"},
      "inertia": {"addr": "D3007", "status": "success"},
      "encoder_res": {"addr": "D3008", "status": "success"},
      "test_type": {"addr": "D3101", "status": "success"},
      "load_level": {"addr": "D3102", "status": "success"},
      "test_speed": {"addr": "D3103", "status": "success"},
      "test_duration": {"addr": "D3104", "status": "success"}
    }
  }
}
```

### 2.4 错误响应
```json
{
  "success": false,
  "timestamp": 1704067200000,
  "error": "写入失败",
  "message": "PLC连接异常或参数格式错误",
  "data": {
    "written_parameters": 8,
    "failed_parameters": 4,
    "write_results": {
      "motor_model": {"addr": "D3001", "status": "success"},
      "rated_voltage": {"addr": "D3002", "status": "failed", "error": "地址不可写"},
      "rated_current": {"addr": "D3003", "status": "failed", "error": "数值超出范围"}
    }
  }
}
```

## 三、通用规范

### 3.1 HTTP状态码
- `200`: 请求成功
- `400`: 请求参数错误
- `401`: 未授权访问
- `404`: 接口不存在
- `500`: 服务器内部错误
- `503`: 服务不可用

### 3.2 错误码定义
- `E001`: 参数格式错误
- `E002`: 必需参数缺失
- `E003`: 设备连接失败
- `E004`: 数据读取超时
- `E005`: 数据写入失败
- `E006`: 地址映射错误
- `E007`: 权限不足

### 3.3 请求头要求
```
Content-Type: application/json
Accept: application/json
```

### 3.4 CORS支持
API支持跨域请求，允许以下来源：
- `http://127.0.0.1:5000`
- `http://localhost:5000`
- `http://127.0.0.1:5500`
- `http://localhost:5500`

## 四、使用示例

### 4.1 JavaScript调用示例

#### 数据采集
```javascript
async function collectData(keys = []) {
  try {
    const response = await fetch('/api/data/collect', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        keys: keys,
        timestamp: Date.now()
      })
    });
    
    const result = await response.json();
    if (result.success) {
      return result.data.values;
    } else {
      throw new Error(result.message);
    }
  } catch (error) {
    console.error('数据采集失败:', error);
    throw error;
  }
}
```

#### 数据写入
```javascript
async function writeMotorConfig(motorConfig, testConfig) {
  try {
    const response = await fetch('/api/data/write', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        motor_config: motorConfig,
        test_config: testConfig
      })
    });
    
    const result = await response.json();
    if (result.success) {
      return result.data;
    } else {
      throw new Error(result.message);
    }
  } catch (error) {
    console.error('配置写入失败:', error);
    throw error;
  }
}
```

## 五、注意事项

1. **数据采集频率**: 建议采集间隔不小于100ms，避免过于频繁的请求
2. **数据写入安全**: 写入操作会直接影响PLC配置，请确保参数正确性
3. **网络超时**: 建议设置5-10秒的请求超时时间
4. **错误处理**: 客户端应实现重试机制和降级策略
5. **数据缓存**: 可在客户端实现适当的数据缓存以提升用户体验

## 六、版本信息

- **文档版本**: v1.0
- **API版本**: v1.0
- **最后更新**: 2025-01-01
- **维护人员**: 系统开发团队