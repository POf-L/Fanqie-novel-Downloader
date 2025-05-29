DEFAULT_WINDOW_GEOMETRY="800x600"

REQUEST_CONFIG = {
    "max_workers": 5,
    "max_retries": 3,
    "request_timeout": 15,
    "use_local_crawler": False,
    "user_agents": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ]
}

READER_CONFIG = {
    "default_font": "Arial",
    "default_size": 12,
    "default_fg": "#000000",
    "default_bg": "#FFFFFF",
    "default_width": 800,
    "default_height": 750,
    "padding": 10
}

FILE_CONFIG = {
    "status_file": "chapter.json",
    "cookie_file": "cookie.json",
    "default_save_path": "downloads"
}

def load_user_config():
    import os
    import json
    
    user_config_path = "user_config.json"
    config = {
        "request": REQUEST_CONFIG.copy(),
        "reader": READER_CONFIG.copy(),
        "file": FILE_CONFIG.copy()
    }
    
    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                
                if "request" in user_config:
                    config["request"].update(user_config["request"])
                if "reader" in user_config:
                    config["reader"].update(user_config["reader"])
                if "file" in user_config:
                    config["file"].update(user_config["file"])
        except Exception as e:
            print(f"加载用户配置失败: {str(e)}")
    
    return config

def save_user_config(config):
    import json
    
    try:
        with open("user_config.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"保存用户配置失败: {str(e)}")
        return False

CONFIG = load_user_config()