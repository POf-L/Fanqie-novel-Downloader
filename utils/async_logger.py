# -*- coding: utf-8 -*-
"""
异步日志模块 - 减少锁竞争，提升下载性能
"""

import asyncio
import sys
from typing import Optional
from datetime import datetime

class AsyncLogger:
    """异步日志器，使用队列避免锁竞争"""
    
    def __init__(self, enable_console: bool = True):
        self.queue = asyncio.Queue()
        self.enable_console = enable_console
        self._task = None
        self._running = False
    
    async def start(self):
        """启动日志处理任务"""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._process_logs())
    
    async def stop(self):
        """停止日志处理"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _process_logs(self):
        """处理日志队列"""
        while self._running:
            try:
                # 等待日志消息，超时继续检查状态
                msg = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                if self.enable_console:
                    print(msg)
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception:
                pass
    
    async def log(self, message: str):
        """异步记录日志"""
        if self._running:
            await self.queue.put(message)
        else:
            # 如果未启动，直接输出
            if self.enable_console:
                print(message)
    
    def sync_log(self, message: str):
        """同步记录日志（兼容旧代码）"""
        if self._running:
            # 在异步环境中，创建任务
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self.log(message))
            except RuntimeError:
                # 不在异步环境中，直接输出
                if self.enable_console:
                    print(message)
        else:
            if self.enable_console:
                print(message)

# 全局异步日志实例
async_logger = AsyncLogger()

async def init_async_logger():
    """初始化异步日志系统"""
    await async_logger.start()

async def shutdown_async_logger():
    """关闭异步日志系统"""
    await async_logger.stop()

def async_print(message: str):
    """替代print的异步输出函数"""
    async_logger.sync_log(message)

# 兼容性函数，用于替换print_lock的使用
def safe_print(message: str):
    """安全打印，避免锁竞争"""
    async_logger.sync_log(message)
