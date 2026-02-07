# 🔧 节点管理和故障恢复

## 📋 概述

节点管理功能实现了启动时异步测试所有 API 节点，优选最快且支持批量下载的节点，并提供持续的节点健康监控和故障恢复机制。

## ✨ 功能特性

### 1. 启动时节点测试
- 程序启动时自动异步测试所有配置的 API 节点
- 测试节点连通性、延迟和批量下载支持
- 优先选择支持批量下载且延迟最低的节点
- 测试过程不阻塞程序启动

### 2. 动态节点切换
- APIManager 会优先使用节点测试器选择的最优节点
- 支持运行时动态更新最优节点
- 提供节点状态信息查询接口

### 3. 节点状态缓存
- 将节点测试结果持久化到本地缓存
- 支持缓存过期管理（默认 72 小时）
- 提供可用节点和优选节点快速查询

### 4. 健康监控
- 后台定期检查节点健康状态（默认 5 分钟间隔）
- 自动检测节点故障和恢复
- 维护故障节点列表

### 5. 故障恢复
- 当前节点故障时自动切换到备用节点
- 优先切换到支持批量下载的可用节点
- 支持手动触发故障恢复

## 🏗️ 文件结构

```
utils/
├── node_manager.py    # 节点测试、状态缓存和故障恢复（包含 NodeTester、NodeStatusCache、NodeHealthMonitor、NodeFailureRecovery 类）
└── ...

core/
├── novel_downloader.py # 支持动态节点切换
└── ...

main.py                # 集成启动时异步节点测试
web/web_app.py         # 集成故障恢复器初始化
```

## 🎯 主要类和函数

### NodeTester (utils/node_manager.py)

节点测试和优选模块，负责测试所有节点并选择最优节点。

**主要方法**：
- `test_all_nodes_async()`: 异步测试所有节点
- `run_optimal_node_selection()`: 运行节点优选流程
- `get_optimal_node()`: 获取当前最优节点

**使用示例**：
```python
from utils.node_manager import NodeTester

# 创建节点测试器
tester = NodeTester(config)

# 异步测试所有节点
await tester.test_all_nodes_async()

# 获取最优节点
optimal_node = tester.get_optimal_node()
print(f"最优节点: {optimal_node}")
```

### NodeStatusCache (utils/node_manager.py)

节点状态缓存模块，负责持久化节点状态。

**主要方法**：
- `update_node_status()`: 更新节点状态
- `get_preferred_nodes()`: 获取优选节点列表
- `clean_expired_cache()`: 清理过期缓存

**使用示例**：
```python
from utils.node_manager import NodeStatusCache

# 创建状态缓存
cache = NodeStatusCache(cache_file="node_status.json")

# 更新节点状态
cache.update_node_status(node_url, status="healthy", latency=100)

# 获取优选节点
preferred = cache.get_preferred_nodes()
for node in preferred:
    print(f"节点: {node['url']}, 延迟: {node['latency']}ms")
```

### NodeHealthMonitor (utils/node_manager.py)

节点健康监控模块，负责定期检查节点状态。

**主要方法**：
- `start_monitoring()`: 启动健康监控
- `get_failed_nodes()`: 获取故障节点列表
- `force_check_node()`: 强制检查单个节点

**使用示例**：
```python
from utils.node_manager import NodeHealthMonitor

# 创建健康监控器
monitor = NodeHealthMonitor(api_sources, check_interval=300)

# 启动监控（后台线程）
monitor.start_monitoring()

# 获取故障节点
failed_nodes = monitor.get_failed_nodes()
print(f"故障节点: {failed_nodes}")

# 强制检查单个节点
monitor.force_check_node(node_url)
```

### NodeFailureRecovery (utils/node_manager.py)

故障恢复模块，负责节点故障时的自动切换。

**主要方法**：
- `try_recovery()`: 尝试故障恢复
- `get_recovery_status()`: 获取恢复状态

**使用示例**：
```python
from utils.node_manager import NodeFailureRecovery

# 创建故障恢复器
recovery = NodeFailureRecovery(node_status_cache, api_sources)

# 尝试故障恢复
success = recovery.try_recovery(failed_node_url)
if success:
    print("故障恢复成功")
else:
    print("故障恢复失败")

# 获取恢复状态
status = recovery.get_recovery_status()
print(f"恢复状态: {status}")
```

## ⚙️ 配置说明

### 节点配置

节点配置在 `config/fanqie.json` 中：

```json
{
  "api_sources": [
    {
      "base_url": "https://api1.example.com",
      "supports_full_download": true
    },
    {
      "base_url": "https://api2.example.com",
      "supports_full_download": false
    }
  ]
}
```

**配置项说明**：
- `base_url`: API 节点地址
- `supports_full_download`: 是否支持批量下载（优选考虑）

### 缓存配置

```json
{
  "cache": {
    "file": "fanqie_node_status_cache.json",
    "expire_hours": 72
  }
}
```

**配置项说明**：
- `file`: 缓存文件路径（相对于程序目录，默认为 `fanqie_node_status_cache.json`）
- `expire_hours`: 缓存过期时间（小时）

**缓存文件位置**：
- **Windows**: `%TEMP%/fanqie_node_status_cache.json`
- **macOS**: `/tmp/fanqie_node_status_cache.json`
- **Linux**: `/tmp/fanqie_node_status_cache.json`

### 监控配置

```json
{
  "monitoring": {
    "check_interval": 300,
    "timeout": 10,
    "retry_times": 3
  }
}
```

**配置项说明**：
- `check_interval`: 健康检查间隔（秒）
- `timeout`: 请求超时时间（秒）
- `retry_times`: 重试次数

## 🚀 使用流程

### 启动时

1. 程序启动后立即开始异步测试所有节点
2. 测试完成后选择最优节点（支持批量下载 + 延迟最低）
3. 初始化健康监控和故障恢复器
4. APIManager 使用选择的最优节点

**代码示例**：
```python
# main.py
from utils.node_manager import NodeTester, NodeStatusCache, NodeHealthMonitor, NodeFailureRecovery

# 启动节点测试
tester = NodeTester(config)
async def startup():
    await tester.test_all_nodes_async()
    optimal_node = tester.get_optimal_node()
    
    # 初始化监控和恢复
    cache = NodeStatusCache()
    monitor = NodeHealthMonitor(api_sources)
    recovery = NodeFailureRecovery(cache, api_sources)
    
    monitor.start_monitoring()

# 启动程序
asyncio.run(startup())
```

### 运行时

1. 健康监控定期检查节点状态
2. 发现节点故障时标记为故障状态
3. API 请求失败时尝试故障恢复
4. 自动切换到可用的备用节点

**代码示例**：
```python
# web/web_app.py
from utils.node_manager import NodeFailureRecovery

# 初始化故障恢复器
recovery = NodeFailureRecovery(cache, api_sources)

# API 请求失败时的处理
try:
    response = requests.get(f"{node_url}/api/...")
except requests.exceptions.RequestException as e:
    # 尝试故障恢复
    new_node = recovery.try_recovery(node_url)
    if new_node:
        # 使用新节点重试
        try:
            response = requests.get(f"{new_node}/api/...")
        except requests.exceptions.RequestException as retry_error:
            # 新节点也失败，返回错误
            return {"error": f"所有节点均不可用: {str(retry_error)}"}, 503
    else:
        # 没有可用节点，返回错误
        return {"error": "无可用节点，请稍后重试"}, 503
```

### 故障恢复策略

1. 优先从支持批量下载的可用节点中选择
2. 如果没有，从任何可用节点中选择
3. 按缓存中的延迟排序，选择延迟最低的

## 📊 性能优化

### 并发测试
- 使用线程池进行并发节点测试
- 减少测试时间，提升启动速度

### 状态缓存
- 节点状态缓存避免重复测试
- 减少网络请求，提升性能

### 速率控制
- 令牌桶算法控制请求速率
- 避免对服务器造成压力

### 异步操作
- 异步操作减少启动阻塞
- 提升用户体验

## 🔍 监控和调试

### 查看节点测试结果

```python
# 查看控制台输出的节点测试结果
# 程序启动时会输出所有节点的测试结果
```

### 查看当前状态

```python
from utils.node_manager import get_node_status_info

# 获取节点状态信息
status_info = get_node_status_info()
print(json.dumps(status_info, indent=2))
```

### 检查缓存文件

```bash
# 查看缓存文件
# Windows
type %TEMP%\fanqie_node_status_cache.json

# macOS/Linux
cat /tmp/fanqie_node_status_cache.json
```

### 手动触发节点测试

```python
from utils.node_manager import NodeTester

# 创建测试器
tester = NodeTester(config)

# 手动测试所有节点
await tester.test_all_nodes_async()

# 获取测试结果
results = tester.get_test_results()
for node, result in results.items():
    print(f"{node}: {result}")
```

## ⚠️ 注意事项

1. **线程池隔离**：节点测试使用独立的线程池，不影响主程序
2. **守护线程**：健康监控为守护线程，程序退出时自动结束
3. **缓存位置**：缓存文件存储在系统临时目录（Windows: `%TEMP%`, macOS/Linux: `/tmp`）
4. **故障恢复**：故障恢复仅在启用时生效
5. **超时控制**：所有网络请求都有超时控制，避免长时间阻塞
6. **缓存过期**：缓存默认 72 小时过期，需要定期清理
7. **网络依赖**：节点测试需要网络连接，离线环境下无法使用

## 🐛 故障排除

### 问题1：节点测试失败

**症状**：所有节点测试都失败

**解决方案**：
1. 检查网络连接
2. 检查防火墙设置
3. 检查节点配置是否正确
4. 查看错误日志

### 问题2：节点切换频繁

**症状**：节点频繁切换，影响使用

**解决方案**：
1. 增加健康检查间隔
2. 调整故障阈值
3. 检查网络稳定性
4. 使用更稳定的节点

### 问题3：缓存文件损坏

**症状**：无法读取缓存文件

**解决方案**：
1. 删除缓存文件
2. 重新运行程序
3. 程序会自动重建缓存

## 📚 相关文档

- [本地安装指南](LOCAL_INSTALLATION.md)
- [贡献指南](CONTRIBUTING.md)
- [项目架构](../README.md#项目结构)

---

📖 **返回主文档**: [README.md](../README.md)
