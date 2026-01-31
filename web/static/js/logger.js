/* ===================== 日志管理 ===================== */

const Logger = {
    logs: [],
    maxLogs: 100,

    logKey(key, ...args) {
        const messages = {
            msg_app_start: ['应用启动', 'info'],
            msg_token_loaded: ['访问令牌已加载', 'info'],
            msg_ready: ['就绪', 'success'],
            msg_init_partial: ['部分初始化', 'warning'],
            msg_check_network: ['请检查网络连接', 'warning'],
            msg_save_path_updated: ['保存路径已更新', 'info'],
            msg_search_start: ['开始搜索', 'info'],
            msg_search_success: ['搜索成功', 'success'],
            msg_search_empty: ['未找到结果', 'info'],
            msg_download_start: ['开始下载', 'info'],
            msg_download_complete: ['下载完成', 'success'],
            msg_download_failed: ['下载失败', 'error'],
            msg_queue_added: ['已添加到队列', 'info'],
            msg_queue_cleared: ['队列已清空', 'info'],
            msg_node_switched: ['节点已切换', 'info'],
            msg_node_failed: ['节点不可用', 'error']
        };

        const [defaultMsg, level] = messages[key] || [key, 'info'];
        const msg = args.length > 0 ? `${defaultMsg}: ${args[0]}` : defaultMsg;
        this.log(msg, level, key);
    },

    log(message, level = 'info', key = null) {
        const logEntry = {
            timestamp: new Date().toLocaleString('zh-CN'),
            message,
            level,
            key
        };

        this.logs.unshift(logEntry);
        if (this.logs.length > this.maxLogs) {
            this.logs.pop();
        }

        this.render();
    },

    render() {
        const primary = document.getElementById('logContentMain');
        const fallback = document.getElementById('logContainer');
        const html = this.logs.map(log => `
            <div class="log-entry log-${log.level}">
                <span class="log-time">${log.timestamp}</span>
                <span class="log-message">${log.message}</span>
            </div>
        `).join('');

        if (primary) primary.innerHTML = html;
        if (fallback) fallback.innerHTML = html;
    },

    clear() {
        this.logs = [];
        this.render();
    },

    getText() {
        return this.logs.map(log => `[${log.timestamp}] ${log.message}`).join('\n');
    }
};

export default Logger;
