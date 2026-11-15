# -*- coding: utf-8 -*-
"""配置与本地数据持久化。运行时文件全部收进隐藏目录，解压目录只留一个 exe。"""
import json
import os
import shutil
import sys
import threading

APP_NAME = "读一下"
BUILD = 5                       # 用于识别后台旧版实例并请其退出
APP_DIR = os.path.dirname(os.path.abspath(__file__))
_FROZEN = getattr(sys, "frozen", False)
if _FROZEN:
    ROOT_DIR = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    ROOT_DIR = os.path.dirname(APP_DIR)
    BUNDLE_DIR = APP_DIR

WEB_DIR = os.path.join(BUNDLE_DIR, "web")
# 第三方依赖见根目录 requirements.txt；源码运行时由 pip 安装，frozen 构建时由 PyInstaller 打入
VENDOR_DIR = os.path.join(BUNDLE_DIR, "vendor")
ICON_PATH = os.path.join(BUNDLE_DIR, "icon.ico")
# 所有运行时数据集中到隐藏 + 系统属性目录，资源管理器默认不可见
RUNTIME_DIR = os.path.join(ROOT_DIR, ".duyixia")
DATA_DIR = RUNTIME_DIR
CONFIG_PATH = os.path.join(RUNTIME_DIR, "config.json")
HISTORY_PATH = os.path.join(RUNTIME_DIR, "history.json")
FAVORITE_PATH = os.path.join(RUNTIME_DIR, "favorites.json")
CACHE_DIR = os.path.join(RUNTIME_DIR, "cache")
PROFILE_DIR = os.path.join(RUNTIME_DIR, "profile")

for _d in (RUNTIME_DIR, CACHE_DIR, PROFILE_DIR):
    if not os.path.isdir(_d):
        os.makedirs(_d, exist_ok=True)

VOICES = [
    {"id": "en-US-AriaNeural", "name": "Aria · 美式女声", "desc": "清晰自然，推荐日常听读"},
    {"id": "en-US-JennyNeural", "name": "Jenny · 美式女声", "desc": "柔和亲切，适合单词学习"},
    {"id": "en-US-GuyNeural", "name": "Guy · 美式男声", "desc": "沉稳标准，新闻播报风格"},
    {"id": "en-US-EricNeural", "name": "Eric · 美式男声", "desc": "年轻明快，语速利落"},
]

DEFAULTS = {
    "voice": "en-US-AriaNeural",
    "word_voice": "dict",           # dict=单词走词典真人发音(0.2s) / edge=统一神经音(2s)
    "hotkey": "Ctrl+Shift+S",
    "hotkey_mods": 0x0002 | 0x0004,
    "hotkey_vk": 0x53,
    "start_minimized": False,      # 启动只驻留托盘
    "tray_auto_open": False,       # 关窗后按热键自动打开主窗口
    "show_balloon": True,          # 关窗后用通知气泡显示译文
    "theme": "light",
    "translate_engine": "baidu",       # baidu | auto | free | custom
    "baidu_appid": "",
    "baidu_secret": "",
    "custom_api_url": "",
    "custom_api_key": "",
    "target_lang": "zh-CN",
    "auto_speak": True,
    "auto_translate": True,
    "auto_phonics": True,
    "minimize_to_tray": True,
    "autostart": False,
    "history_limit": 200,
    "port": 21876,
}

_lock = threading.Lock()


def _hide_dir(path):
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(
                ctypes.c_wchar_p(path), 0x0002 | 0x0004)  # HIDDEN | SYSTEM
        except Exception:
            pass


def _read(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def _write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    _hide_dir(os.path.dirname(path))


def _migrate_legacy():
    """把旧版散落在 exe 同目录的 config.json / data 收进隐藏目录并清掉。"""
    old_cfg = os.path.join(ROOT_DIR, "config.json")
    if os.path.isfile(old_cfg):
        try:
            with open(old_cfg, "r", encoding="utf-8") as f:
                old = json.load(f)
            if isinstance(old, dict) and ("voice" in old or "hotkey" in old):
                if old.get("translate_engine") == "auto":
                    old["translate_engine"] = "baidu"   # 旧版 auto 语义升级
                old["port"] = 21876                     # 与旧版端口隔离，避免误启动旧程序时冲突
                cur = _read(CONFIG_PATH, {})
                cur.update(old)
                _write(CONFIG_PATH, cur)
                os.remove(old_cfg)
        except Exception:
            pass
    old_data = os.path.join(ROOT_DIR, "data")
    if os.path.isdir(old_data):
        try:
            names = os.listdir(old_data)
            allowed = {"tray.ico", "app.log", "cache", "profile",
                       "history.json", "favorites.json"}
            if all(n in allowed for n in names):
                for n in ("history.json", "favorites.json"):
                    p = os.path.join(old_data, n)
                    if os.path.isfile(p) and not os.path.isfile(os.path.join(RUNTIME_DIR, n)):
                        shutil.copy2(p, os.path.join(RUNTIME_DIR, n))
                shutil.rmtree(old_data, ignore_errors=True)
        except Exception:
            pass


_hide_dir(RUNTIME_DIR)
_migrate_legacy()


def load_config():
    cfg = dict(DEFAULTS)
    cfg.update(_read(CONFIG_PATH, {}))
    with _lock:
        _write(CONFIG_PATH, cfg)
    return cfg


def save_config(cfg):
    with _lock:
        old = _read(CONFIG_PATH, {})
        old.update(cfg)
        _write(CONFIG_PATH, old)
    return old


def load_history():
    return _read(HISTORY_PATH, [])


def add_history(item, limit=200):
    with _lock:
        items = [x for x in _read(HISTORY_PATH, []) if x.get("text") != item.get("text")]
        items.insert(0, item)
        items = items[:limit]
        _write(HISTORY_PATH, items)
    return items


def clear_history():
    with _lock:
        _write(HISTORY_PATH, [])


def load_favorites():
    return _read(FAVORITE_PATH, [])


def toggle_favorite(item):
    with _lock:
        items = _read(FAVORITE_PATH, [])
        key = item.get("text")
        rest = [x for x in items if x.get("text") != key]
        added = len(rest) == len(items)
        if added:
            rest.insert(0, item)
        _write(FAVORITE_PATH, rest)
    return added, rest


def remove_favorite(text):
    with _lock:
        items = [x for x in _read(FAVORITE_PATH, []) if x.get("text") != text]
        _write(FAVORITE_PATH, items)
    return items
