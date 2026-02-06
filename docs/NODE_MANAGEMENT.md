# -*- coding: utf-8 -*-
"""
节点管理功能使用说明

本功能实现了启动时异步测试所有API节点，优选最快且支持批量下载的节点，
并提供持续的节点健康监控和故障恢复机制。

## 功能特性

### 1. 启动时节点测试
- 程序启动时自动异步测试所有配置的API节点
- 测试节点连通性、延迟和批量下载支持
- 优先选择支持批量下载且延迟最低的节点
- 测试过程不阻塞程序启动

### 2. 动态节点切换
- APIManager会优先使用节点测试器选择的最优节点
- 支持运行时动态更新最优节点
- 提供节点状态信息查询接口

### 3. 节点状态缓存
- 将节点测试结果持久化到本地缓存
- 支持缓存过期管理（默认72小时）
- 提供可用节点和优选节点快速查询

### 4. 健康监控
- 后台定期检查节点健康状态（默认5分钟间隔）
- 自动检测节点故障和恢复
- 维护故障节点列表

### 5. 故障恢复
- 当前节点故障时自动切换到备用节点
- 优先切换到支持批量下载的可用节点
- 支持手动触发故障恢复

## 文件结构

```
utils/
├── node_tester.py     # 节点测试和优选模块
├── node_manager.py    # 节点状态缓存和故障恢复
└── ...

core/
├── novel_downloader.py # 修改后支持动态节点切换
└── ...

main.py                # 集成启动时异步节点测试
web/web_app.py         # 集成故障恢复器初始化
```

## 主要类和函数

### NodeTester (utils/node_tester.py)
- `test_all_nodes_async()`: 异步测试所有节点
- `run_optimal_node_selection()`: 运行节点优选流程
- `get_optimal_node()`: 获取当前最优节点

### NodeStatusCache (utils/node_manager.py)
- `update_node_status()`: 更新节点状态
- `get_preferred_nodes()`: 获取优选节点列表
- `clean_expired_cache()`: 清理过期缓存

### NodeHealthMonitor (utils/node_manager.py)
- `start_monitoring()`: 启动健康监控
- `get_failed_nodes()`: 获取故障节点列表
- `force_check_node()`: 强制检查单个节点

### NodeFailureRecovery (utils/node_manager.py)
- `try_recovery()`: 尝试故障恢复
- `get_recovery_status()`: 获取恢复状态

## 配置说明

节点配置在 `config/fanqie.json` 中：

```json
{
  "api_sources": [
    {"base_url": "https://api1.example.com", "supports_full_download": true},
    {"base_url": "https://api2.example.com", "supports_full_download": false}
  ]
}
```

- `base_url`: API节点地址
- `supports_full_download`: 是否支持批量下载（优选考虑）

## 使用流程

### 启动时
1. 程序启动后立即开始异步测试所有节点
2. 测试完成后选择最优节点（支持批量下载 + 延迟最低）
3. 初始化健康监控和故障恢复器
4. APIManager使用选择的最优节点

### 运行时
1. 健康监控定期检查节点状态
2. 发现节点故障时标记为故障状态
3. API请求失败时尝试故障恢复
4. 自动切换到可用的备用节点

### 故障恢复策略
1. 优先从支持批量下载的可用节点中选择
2. 如果没有，从任何可用节点中选择
3. 按缓存中的延迟排序，选择延迟最低的

## 性能优化

- 使用线程池进行并发节点测试
- 节点状态缓存避免重复测试
- 令牌桶算法控制请求速率
- 异步操作减少启动阻塞

## 监控和调试

- 查看控制台输出的节点测试结果
- 使用 `get_node_status_info()` 查看当前状态
- 检查临时目录中的缓存文件 `fanqie_node_status_cache.json`

## 注意事项

1. 节点测试使用独立的线程池，不影响主程序
2. 健康监控为守护线程，程序退出时自动结束
3. 缓存文件存储在系统临时目录
4. 故障恢复仅在启用时生效
5. 所有网络请求都有超时控制，避免长时间阻塞
