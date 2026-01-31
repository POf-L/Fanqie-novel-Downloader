import re

file_path = r"D:\项目\Fanqie-novel-Downloader\web\templates\index.html"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 移除 Header API Source
pattern_header = re.compile(r'\s+<div class="header-api-source">[\s\S]*?</div>', re.MULTILINE)
content = pattern_header.sub('', content, count=1)

# 2. 替换 Settings 内容
new_settings_html = """                            <div class="settings-container settings-layout">
                                <div class="settings-sidebar">
                                    <button class="settings-nav-btn active" data-section="basic">
                                        <iconify-icon icon="line-md:download-loop"></iconify-icon>
                                        基本设置
                                    </button>
                                    <button class="settings-nav-btn" data-section="advanced">
                                        <iconify-icon icon="line-md:backup-restore"></iconify-icon>
                                        高级设置
                                    </button>
                                    <button class="settings-nav-btn" data-section="api">
                                        <iconify-icon icon="line-md:cloud-up-twotone-loop"></iconify-icon>
                                        接口设置
                                    </button>
                                </div>
                                <div class="settings-content">
                                    <!-- 基本设置 -->
                                    <div class="settings-section active" id="section-basic">
                                        <h3 class="settings-section-title">下载设置</h3>
                                        <div class="settings-grid">
                                            <div class="setting-item setting-item-slider">
                                                <div class="setting-header">
                                                    <label class="setting-label">最大并发数</label>
                                                    <span class="setting-value" id="setting_max_workers_value">30</span>
                                                </div>
                                                <div class="setting-control">
                                                    <input type="range" id="setting_max_workers_range" class="setting-slider" min="1" max="100" value="30">
                                                    <input type="number" id="setting_max_workers" class="form-input setting-number" min="1" max="100" value="30">
                                                </div>
                                                <span class="setting-hint">同时下载的任务数量</span>
                                            </div>
                                            <div class="setting-item setting-item-slider">
                                                <div class="setting-header">
                                                    <label class="setting-label">连接池大小</label>
                                                    <span class="setting-value" id="setting_connection_pool_size_value">200</span>
                                                </div>
                                                <div class="setting-control">
                                                    <input type="range" id="setting_connection_pool_size_range" class="setting-slider" min="10" max="500" value="200">
                                                    <input type="number" id="setting_connection_pool_size" class="form-input setting-number" min="10" max="500" value="200">
                                                </div>
                                                <span class="setting-hint">HTTP连接池的大小</span>
                                            </div>
                                            <div class="setting-item setting-item-slider">
                                                <div class="setting-header">
                                                    <label class="setting-label">异步批次大小</label>
                                                    <span class="setting-value" id="setting_async_batch_size_value">50</span>
                                                </div>
                                                <div class="setting-control">
                                                    <input type="range" id="setting_async_batch_size_range" class="setting-slider" min="1" max="200" value="50">
                                                    <input type="number" id="setting_async_batch_size" class="form-input setting-number" min="1" max="200" value="50">
                                                </div>
                                                <span class="setting-hint">每批次处理的任务数</span>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- 高级设置 -->
                                    <div class="settings-section" id="section-advanced">
                                        <h3 class="settings-section-title">高级设置</h3>
                                        <div class="settings-grid">
                                            <div class="setting-item setting-item-slider">
                                                <div class="setting-header">
                                                    <label class="setting-label">最大重试次数</label>
                                                    <span class="setting-value" id="setting_max_retries_value">3</span>
                                                </div>
                                                <div class="setting-control">
                                                    <input type="range" id="setting_max_retries_range" class="setting-slider" min="0" max="10" value="3">
                                                    <input type="number" id="setting_max_retries" class="form-input setting-number" min="0" max="10" value="3">
                                                </div>
                                                <span class="setting-hint">失败后最多重试次数</span>
                                            </div>
                                            <div class="setting-item setting-item-slider">
                                                <div class="setting-header">
                                                    <label class="setting-label">请求超时(秒)</label>
                                                    <span class="setting-value" id="setting_request_timeout_value">30</span>
                                                </div>
                                                <div class="setting-control">
                                                    <input type="range" id="setting_request_timeout_range" class="setting-slider" min="5" max="300" value="30">
                                                    <input type="number" id="setting_request_timeout" class="form-input setting-number" min="5" max="300" value="30">
                                                </div>
                                                <span class="setting-hint">单个请求的超时时间</span>
                                            </div>
                                            <div class="setting-item setting-item-slider">
                                                <div class="setting-header">
                                                    <label class="setting-label">请求间隔(秒)</label>
                                                    <span class="setting-value" id="setting_request_rate_limit_value">0.02</span>
                                                </div>
                                                <div class="setting-control">
                                                    <input type="range" id="setting_request_rate_limit_range" class="setting-slider" min="0" max="1000" value="20">
                                                    <input type="number" id="setting_request_rate_limit" class="form-input setting-number" min="0" max="10" step="0.01" value="0.02">
                                                </div>
                                                <span class="setting-hint">每次请求之间的延迟</span>
                                            </div>
                                            <div class="setting-item setting-item-slider">
                                                <div class="setting-header">
                                                    <label class="setting-label">API速率限制</label>
                                                    <span class="setting-value" id="setting_api_rate_limit_value">50</span>
                                                </div>
                                                <div class="setting-control">
                                                    <input type="range" id="setting_api_rate_limit_range" class="setting-slider" min="1" max="200" value="50">
                                                    <input type="number" id="setting_api_rate_limit" class="form-input setting-number" min="1" max="200" value="50">
                                                </div>
                                                <span class="setting-hint">每秒最大请求数</span>
                                            </div>
                                            <div class="setting-item setting-item-slider">
                                                <div class="setting-header">
                                                    <label class="setting-label">速率窗口(秒)</label>
                                                    <span class="setting-value" id="setting_rate_limit_window_value">1.0</span>
                                                </div>
                                                <div class="setting-control">
                                                    <input type="range" id="setting_rate_limit_window_range" class="setting-slider" min="1" max="100" value="10">
                                                    <input type="number" id="setting_rate_limit_window" class="form-input setting-number" min="0.1" max="10" step="0.1" value="1.0">
                                                </div>
                                                <span class="setting-hint">速率计算的时间窗口</span>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- 接口设置 -->
                                    <div class="settings-section" id="section-api">
                                         <h3 class="settings-section-title">下载接口</h3>
                                         <div class="api-setting-panel">
                                             <div class="api-mode-switch">
                                                <label class="radio-label">
                                                    <input type="radio" name="apiMode" value="auto"> 自动选择 (推荐)
                                                </label>
                                                <label class="radio-label">
                                                    <input type="radio" name="apiMode" value="manual"> 手动选择
                                                </label>
                                             </div>
                                             
                                             <div class="api-status-card" id="currentApiStatus">
                                                <div class="status-row">
                                                    <span class="status-label">当前节点:</span>
                                                    <strong class="status-value" id="currentApiUrl">-</strong>
                                                </div>
                                                <div class="status-row">
                                                    <span class="status-label">延迟:</span>
                                                    <span class="status-value" id="currentApiLatency">-</span>
                                                </div>
                                             </div>

                                             <div class="api-list-container" id="apiListContainer">
                                                <!-- API List injected here -->
                                             </div>
                                             
                                             <button class="btn btn-secondary btn-sm" id="refreshApiListBtn" style="margin-top: 10px;">
                                                <iconify-icon icon="line-md:rotate-clockwise"></iconify-icon> 刷新列表
                                             </button>
                                         </div>
                                    </div>
                                </div>
                                
                                <div class="settings-footer">
                                    <div class="settings-message" id="settingsMessage" style="display: none;"></div>
                                    <div class="settings-actions">
                                        <button class="btn btn-primary" id="saveSettingsBtn">
                                            <iconify-icon icon="line-md:confirm"></iconify-icon>
                                            <span>保存设置</span>
                                        </button>
                                        <button class="btn btn-secondary" id="resetSettingsBtn">
                                            <iconify-icon icon="line-md:close"></iconify-icon>
                                            <span>恢复默认</span>
                                        </button>
                                    </div>
                                </div>
                            </div>"""

start_marker = '<div class="settings-container">'
end_marker = '<!-- 加载状态遮罩层 -->'

start_pos = content.find(start_marker)
end_pos = content.find(end_marker)

if start_pos != -1 and end_pos != -1:
    before_overlay = content[:end_pos]
    r_div1 = before_overlay.rfind('</div>')
    r_div2 = before_overlay.rfind('</div>', 0, r_div1)
    
    if r_div2 != -1:
        content = content[:start_pos] + new_settings_html + content[r_div2+6:]
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Successfully modified index.html")
    else:
        print("Could not find closing div for settings-container")
else:
    print(f"Could not find markers: start={start_pos}, end={end_pos}")
