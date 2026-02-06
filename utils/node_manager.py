# -*- coding: utf-8 -*-
"""
节点管理模块
提供节点测试、状态缓存、健康监控和故障恢复的完整解决方案
包含节点优选、性能测试、状态持久化和自动故障切换功能
"""

import json
import time
import os
import threading
import asyncio
import requests
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.async_logger import safe_print


class NodeTester:
    """API节点测试器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.api_sources = config.get('api_sources', [])
        self.endpoints = config.get('endpoints', {})
        self.request_timeout = config.get('request_timeout', 30)
        self._test_results = {}
        self._optimal_node = None
        self._test_lock = threading.Lock()
        
    def _test_node_sync(self, base_url: str, supports_full_download: bool = True) -> Dict:
        """同步测试单个节点"""
        base_url = base_url.strip().rstrip('/')

        # 使用搜索接口测试节点可用性（所有节点都应该有这个接口）
        search_url = f"{base_url}/api/search"
        test_result = {
            'base_url': base_url,
            'supports_full_download': supports_full_download,
            'available': False,
            'latency_ms': None,
            'error': None,
            'batch_support_verified': False
        }

        try:
            # 测试搜索接口（使用一个通用的搜索关键词）
            start_time = time.time()
            response = requests.get(
                search_url,
                params={"key": "test", "tab_type": "3"},
                timeout=5,
                verify=False
            )
            latency_ms = int((time.time() - start_time) * 1000)

            # 检查响应是否为有效的 JSON
            if response.status_code < 500:
                try:
                    # 尝试解析 JSON
                    data = response.json()

                    # 检查是否包含预期的字段
                    if isinstance(data, dict) and 'code' in data:
                        test_result['available'] = True
                        test_result['latency_ms'] = latency_ms

                        # 如果声明支持批量下载，验证一下
                        if supports_full_download:
                            try:
                                # 测试目录接口（批量下载相关）
                                directory_url = f"{base_url}/api/directory"
                                dir_response = requests.get(
                                    directory_url,
                                    params={"fq_id": "test"},
                                    timeout=5,
                                    verify=False
                                )
                                # 检查目录接口是否返回 JSON
                                try:
                                    dir_data = dir_response.json()
                                    if isinstance(dir_data, dict) and 'code' in dir_data:
                                        test_result['batch_support_verified'] = True
                                    else:
                                        test_result['batch_support_verified'] = False
                                except:
                                    test_result['batch_support_verified'] = False
                            except:
                                test_result['batch_support_verified'] = False
                        else:
                            test_result['batch_support_verified'] = False
                    else:
                        # 响应不是预期的 JSON 格式
                        test_result['error'] = "响应格式错误"
                except:
                    # 响应不是 JSON，可能是防护页面
                    test_result['error'] = "响应非JSON格式"
            else:
                test_result['error'] = f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            test_result['error'] = "超时"
        except requests.exceptions.ConnectionError:
            test_result['error'] = "连接失败"
        except Exception as e:
            test_result['error'] = str(e)[:50]

        return test_result
    
    def test_all_nodes_sync(self) -> List[Dict]:
        """同步测试所有节点（用于CLI工具）"""
        results = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            for source in self.api_sources:
                if isinstance(source, dict):
                    base_url = source.get('base_url', '')
                    supports_full = source.get('supports_full_download', True)
                else:
                    base_url = str(source)
                    supports_full = True
                    
                if base_url:
                    future = executor.submit(self._test_node_sync, base_url, supports_full)
                    futures.append(future)
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    safe_print(f"节点测试异常: {e}")
        
        return results
    
    async def test_all_nodes_async(self) -> List[Dict]:
        """异步测试所有节点（用于启动时）"""
        loop = asyncio.get_event_loop()
        
        # 使用线程池执行同步的网络请求
        with ThreadPoolExecutor(max_workers=10) as executor:
            tasks = []
            
            for source in self.api_sources:
                if isinstance(source, dict):
                    base_url = source.get('base_url', '')
                    supports_full = source.get('supports_full_download', True)
                else:
                    base_url = str(source)
                    supports_full = True
                    
                if base_url:
                    task = loop.run_in_executor(
                        executor, 
                        self._test_node_sync, 
                        base_url, 
                        supports_full
                    )
                    tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 过滤异常结果
            valid_results = []
            for result in results:
                if isinstance(result, dict):
                    valid_results.append(result)
                else:
                    safe_print(f"节点测试异常: {result}")
            
            return valid_results
    
    def _select_optimal_node(self, results: List[Dict]) -> Optional[str]:
        """根据测试结果选择最优节点"""
        if not results:
            return None
        
        # 分类节点
        full_download_available = []
        other_available = []
        
        for result in results:
            if (result.get('available') and 
                result.get('batch_support_verified') and 
                result.get('supports_full_download')):
                full_download_available.append(result)
            elif result.get('available'):
                other_available.append(result)
        
        # 优先选择支持批量下载的节点中延迟最低的
        if full_download_available:
            full_download_available.sort(key=lambda x: x.get('latency_ms', 999999))
            optimal = full_download_available[0]
            safe_print(f"选择最优节点（支持批量下载）: {optimal['base_url']} "
                      f"(延迟: {optimal['latency_ms']}ms)")
            return optimal['base_url']
        
        # 如果没有支持批量下载的节点，选择可用节点中延迟最低的
        if other_available:
            other_available.sort(key=lambda x: x.get('latency_ms', 999999))
            optimal = other_available[0]
            safe_print(f"选择最优节点（普通模式）: {optimal['base_url']} "
                      f"(延迟: {optimal['latency_ms']}ms)")
            return optimal['base_url']
        
        safe_print("警告: 没有可用的API节点")
        return None
    
    async def run_optimal_node_selection(self) -> Optional[str]:
        """运行节点优选流程"""
        safe_print("开始测试API节点可用性和速度...")
        
        try:
            # 异步测试所有节点
            results = await self.test_all_nodes_async()
            
            with self._test_lock:
                self._test_results = {r['base_url']: r for r in results}
                self._optimal_node = self._select_optimal_node(results)
                
                # 打印测试结果摘要
                available_count = sum(1 for r in results if r.get('available'))
                full_download_count = sum(1 for r in results 
                                        if r.get('available') and r.get('batch_support_verified'))
                
                safe_print(f"节点测试完成: {available_count}/{len(results)} 个可用, "
                          f"{full_download_count} 个支持批量下载")
                
                return self._optimal_node
                
        except Exception as e:
            safe_print(f"节点测试失败: {e}")
            return None
    
    def get_test_results(self) -> Dict[str, Dict]:
        """获取测试结果"""
        with self._test_lock:
            return self._test_results.copy()
    
    def get_optimal_node(self) -> Optional[str]:
        """获取当前最优节点"""
        with self._test_lock:
            return self._optimal_node
    
    def get_node_status_summary(self) -> Dict:
        """获取节点状态摘要"""
        with self._test_lock:
            results = list(self._test_results.values())
            
            if not results:
                return {
                    'total_nodes': 0,
                    'available_nodes': 0,
                    'full_download_nodes': 0,
                    'optimal_node': None,
                    'optimal_latency': None
                }
            
            available_count = sum(1 for r in results if r.get('available'))
            full_download_count = sum(1 for r in results 
                                    if r.get('available') and r.get('batch_support_verified'))
            
            optimal_node = self._optimal_node
            optimal_latency = None
            if optimal_node and optimal_node in self._test_results:
                optimal_latency = self._test_results[optimal_node].get('latency_ms')
            
            return {
                'total_nodes': len(results),
                'available_nodes': available_count,
                'full_download_nodes': full_download_count,
                'optimal_node': optimal_node,
                'optimal_latency': optimal_latency
            }


class NodeStatusCache:
    """节点状态缓存管理器"""
    
    def __init__(self, cache_file: Optional[str] = None):
        if cache_file is None:
            import tempfile
            cache_file = os.path.join(tempfile.gettempdir(), 'fanqie_node_status_cache.json')
        
        self.cache_file = cache_file
        self._cache = {}
        self._lock = threading.Lock()
        self._load_cache()
    
    def _load_cache(self):
        """从文件加载缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._cache = data
                        safe_print(f"已加载节点状态缓存: {len(self._cache)} 个节点")
        except Exception as e:
            safe_print(f"加载节点状态缓存失败: {e}")
            self._cache = {}
    
    def _save_cache(self):
        """保存缓存到文件"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            safe_print(f"保存节点状态缓存失败: {e}")
    
    def update_node_status(self, node_url: str, status: Dict):
        """更新节点状态"""
        with self._lock:
            self._cache[node_url] = {
                **status,
                'last_updated': datetime.now().isoformat(),
                'node_url': node_url
            }
            self._save_cache()
    
    def get_node_status(self, node_url: str) -> Optional[Dict]:
        """获取节点状态"""
        with self._lock:
            return self._cache.get(node_url)
    
    def get_all_status(self) -> Dict[str, Dict]:
        """获取所有节点状态"""
        with self._lock:
            return self._cache.copy()
    
    def get_available_nodes(self, max_age_hours: int = 24) -> List[str]:
        """获取可用的节点列表（按最近测试时间过滤）"""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            available = []
            
            for node_url, status in self._cache.items():
                try:
                    last_updated = datetime.fromisoformat(status.get('last_updated', ''))
                    if (last_updated > cutoff_time and 
                        status.get('available', False)):
                        available.append(node_url)
                except:
                    continue
            
            return available
    
    def get_preferred_nodes(self) -> List[str]:
        """获取优选节点列表（支持批量下载的可用节点）"""
        with self._lock:
            preferred = []
            
            for node_url, status in self._cache.items():
                if (status.get('available', False) and 
                    status.get('batch_support_verified', False) and
                    status.get('supports_full_download', False)):
                    preferred.append(node_url)
            
            # 按延迟排序
            preferred.sort(key=lambda x: self._cache.get(x, {}).get('latency_ms', 999999))
            return preferred
    
    def clean_expired_cache(self, max_age_hours: int = 72):
        """清理过期的缓存条目"""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            expired_keys = []
            
            for node_url, status in self._cache.items():
                try:
                    last_updated = datetime.fromisoformat(status.get('last_updated', ''))
                    if last_updated < cutoff_time:
                        expired_keys.append(node_url)
                except:
                    expired_keys.append(node_url)
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                self._save_cache()
                safe_print(f"清理了 {len(expired_keys)} 个过期的节点缓存")


class NodeHealthMonitor:
    """节点健康监控器"""
    
    def __init__(self, node_tester, status_cache: NodeStatusCache, check_interval: int = 300):
        self.node_tester = node_tester
        self.status_cache = status_cache
        self.check_interval = check_interval  # 检查间隔（秒）
        self._running = False
        self._monitor_thread = None
        self._failed_nodes: Set[str] = set()
        self._lock = threading.Lock()
    
    def start_monitoring(self):
        """启动健康监控"""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        safe_print("节点健康监控已启动")
    
    def stop_monitoring(self):
        """停止健康监控"""
        self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        safe_print("节点健康监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                self._check_all_nodes()
                # 清理过期缓存
                self.status_cache.clean_expired_cache()
            except Exception as e:
                safe_print(f"节点健康检查异常: {e}")
            
            # 等待下次检查
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _check_all_nodes(self):
        """检查所有节点状态"""
        try:
            # 同步检查所有节点
            results = self.node_tester.test_all_nodes_sync()
            
            for result in results:
                node_url = result['base_url']
                
                # 更新缓存
                self.status_cache.update_node_status(node_url, result)
                
                # 检查节点状态变化
                old_status = self.status_cache.get_node_status(node_url)
                was_failed = node_url in self._failed_nodes
                is_available = result.get('available', False)
                
                if is_available and was_failed:
                    # 节点恢复
                    with self._lock:
                        self._failed_nodes.discard(node_url)
                    safe_print(f"节点恢复可用: {node_url}")
                elif not is_available and not was_failed:
                    # 节点故障
                    with self._lock:
                        self._failed_nodes.add(node_url)
                    safe_print(f"节点发生故障: {node_url} - {result.get('error', '未知错误')}")
        
        except Exception as e:
            safe_print(f"检查节点状态失败: {e}")
    
    def get_failed_nodes(self) -> List[str]:
        """获取故障节点列表"""
        with self._lock:
            return list(self._failed_nodes)
    
    def is_node_failed(self, node_url: str) -> bool:
        """检查节点是否故障"""
        with self._lock:
            return node_url in self._failed_nodes
    
    def force_check_node(self, node_url: str) -> Optional[Dict]:
        """强制检查单个节点"""
        try:
            # 从配置中找到节点信息
            api_sources = self.node_tester.config.get('api_sources', [])
            supports_full = True
            
            for source in api_sources:
                if isinstance(source, dict):
                    if source.get('base_url', '') == node_url:
                        supports_full = source.get('supports_full_download', True)
                        break
                elif isinstance(source, str) and source == node_url:
                    break
            
            # 测试节点
            result = self.node_tester._test_node_sync(node_url, supports_full)
            
            # 更新缓存
            self.status_cache.update_node_status(node_url, result)
            
            # 更新故障状态
            with self._lock:
                if result.get('available', False):
                    self._failed_nodes.discard(node_url)
                else:
                    self._failed_nodes.add(node_url)
            
            return result
            
        except Exception as e:
            safe_print(f"强制检查节点失败: {e}")
            return None


class NodeFailureRecovery:
    """节点故障恢复管理器"""
    
    def __init__(self, api_manager, status_cache: NodeStatusCache, health_monitor: NodeHealthMonitor):
        self.api_manager = api_manager
        self.status_cache = status_cache
        self.health_monitor = health_monitor
        self._recovery_enabled = True
    
    def enable_recovery(self):
        """启用故障恢复"""
        self._recovery_enabled = True
    
    def disable_recovery(self):
        """禁用故障恢复"""
        self._recovery_enabled = False
    
    def try_recovery(self) -> bool:
        """尝试故障恢复"""
        if not self._recovery_enabled:
            return False
        
        try:
            # 检查当前节点是否故障
            current_node = self.api_manager.base_url
            if not current_node:
                return False
            
            if self.health_monitor.is_node_failed(current_node):
                safe_print(f"当前节点 {current_node} 故障，尝试切换到备用节点")
                
                # 获取优选节点列表
                preferred_nodes = self.status_cache.get_preferred_nodes()
                
                # 排除当前故障节点
                backup_nodes = [node for node in preferred_nodes if node != current_node]
                
                if backup_nodes:
                    # 切换到第一个备用节点
                    new_node = backup_nodes[0]
                    self.api_manager._switch_base_url(new_node)
                    safe_print(f"已切换到备用节点: {new_node}")
                    return True
                else:
                    # 如果没有优选节点，尝试任何可用节点
                    available_nodes = self.status_cache.get_available_nodes()
                    backup_nodes = [node for node in available_nodes if node != current_node]
                    
                    if backup_nodes:
                        new_node = backup_nodes[0]
                        self.api_manager._switch_base_url(new_node)
                        safe_print(f"已切换到可用节点: {new_node}")
                        return True
            
            return False
            
        except Exception as e:
            safe_print(f"故障恢复失败: {e}")
            return False
    
    def get_recovery_status(self) -> Dict:
        """获取恢复状态"""
        current_node = self.api_manager.base_url
        is_failed = self.health_monitor.is_node_failed(current_node) if current_node else False
        preferred_nodes = self.status_cache.get_preferred_nodes()
        available_nodes = self.status_cache.get_available_nodes()
        
        return {
            'recovery_enabled': self._recovery_enabled,
            'current_node': current_node,
            'current_node_failed': is_failed,
            'preferred_nodes_count': len(preferred_nodes),
            'available_nodes_count': len(available_nodes),
            'backup_nodes': [node for node in preferred_nodes if node != current_node][:3]
        }


# 全局实例
_node_tester: Optional[NodeTester] = None
_status_cache: Optional[NodeStatusCache] = None
_health_monitor: Optional[NodeHealthMonitor] = None
_failure_recovery: Optional[NodeFailureRecovery] = None


def get_node_tester() -> Optional[NodeTester]:
    """获取全局节点测试器实例"""
    global _node_tester
    return _node_tester


def initialize_node_tester(config: Dict) -> NodeTester:
    """初始化全局节点测试器"""
    global _node_tester
    _node_tester = NodeTester(config)
    return _node_tester


async def test_and_select_optimal_node(config: Dict) -> Optional[str]:
    """测试并选择最优节点的便捷函数"""
    tester = initialize_node_tester(config)
    return await tester.run_optimal_node_selection()


def initialize_node_management(node_tester, check_interval: int = 300):
    """初始化节点管理模块"""
    global _status_cache, _health_monitor, _failure_recovery
    
    _status_cache = NodeStatusCache()
    _health_monitor = NodeHealthMonitor(node_tester, _status_cache, check_interval)
    
    # 延迟初始化故障恢复器（需要APIManager实例）
    _failure_recovery = None
    
    return _status_cache, _health_monitor


def initialize_failure_recovery(api_manager):
    """初始化故障恢复器"""
    global _failure_recovery, _health_monitor, _status_cache
    
    if _health_monitor and _status_cache:
        _failure_recovery = NodeFailureRecovery(api_manager, _status_cache, _health_monitor)
        return _failure_recovery
    
    return None


def get_status_cache() -> Optional[NodeStatusCache]:
    """获取状态缓存实例"""
    return _status_cache


def get_health_monitor() -> Optional[NodeHealthMonitor]:
    """获取健康监控实例"""
    return _health_monitor


def get_failure_recovery() -> Optional[NodeFailureRecovery]:
    """获取故障恢复实例"""
    return _failure_recovery
