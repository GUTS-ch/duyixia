# -*- coding: utf-8 -*-
"""读一下 入口：本地服务 + 无边框窗口 + 系统托盘 + 全局热键。"""
import os
import sys
import threading
import time
import traceback

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import config  # noqa: E402
import server  # noqa: E402
import services  # noqa: E402
import win32ext  # noqa: E402

LOG_PATH = os.path.join(config.RUNTIME_DIR, "app.log")
PROFILE_DIR = config.PROFILE_DIR
ICON_PATH = config.ICON_PATH
VBS_PATH = os.path.join(config.ROOT_DIR, "启动.vbs")
_FROZEN = getattr(sys, "frozen", False)
LAUNCH_CMD = ('"%s"' % sys.executable) if _FROZEN else ('wscript.exe "%s"' % VBS_PATH)


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


def main():
    state = server.State()
    state.vbs_path = VBS_PATH
    port = state.port

    win32ext.kill_legacy()                 # 内置清理，不再需要外部 bat
    win32ext.stop_legacy_instance(port)    # 后台旧版会挡住单实例互斥，先请它退出
    win32ext.refresh_tray_icons()          # 清掉旧版本遗留的死图标
    if not win32ext.single_instance():      # 已在运行：只唤起窗口
        win32ext.focus_window(port, PROFILE_DIR)
        return

    try:
        httpd = server.make_server(state, port)
    except OSError:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None, "端口 %d 被其他程序占用，读一下无法启动。请结束占用程序后重试。" % port,
                "读一下", 0x00000010)
        except Exception:
            pass
        return

    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.2},
                     daemon=True).start()
    log("服务启动 127.0.0.1:%d" % port)

    tray_ref = {"obj": None}

    def on_hotkey():
        text = win32ext.grab_selection()      # 轮询替代固定 0.2s 等待
        if not text:
            state.publish("status", {"text": "未取到选中文字，请先选中再按热键"})
            return
        if len(text) > 3000:
            text = text[:3000]
        cfg = state.cfg
        state.last_result = {"text": text, "ts": int(time.time())}
        services.prefetch_all(text, cfg)      # 抓到词瞬间并行预热发音/翻译/词典

        if state.has_subscriber():            # 主窗口开着：交给页面处理
            state.publish("selection", {"text": text, "ts": int(time.time())})
            state.publish("status", {"text": "已抓取 %d 个字符" % len(text)})
            return

        # 主窗口已关到托盘：后端直接朗读 + 通知显示译文，完全不依赖浏览器页面
        def tray_job():
            audio, mime, engine = services.get_tts(
                text, cfg.get("voice", "en-US-AriaNeural"),
                cfg.get("word_voice", "dict"))
            played = win32ext.play_audio(audio, mime, config.CACHE_DIR)
            log("托盘模式朗读 %s | %s | played=%s" % (text[:30], engine, played))
            if cfg.get("show_balloon", True):
                tr = services.translate(text, cfg)
                body = ("%s\n%s" % (text[:70], tr.get("text", "")[:150])
                        if tr.get("ok") else text[:200])
                tray = tray_ref["obj"]
                if tray:
                    tray._safe(tray.balloon, "读一下", body)
            if cfg.get("tray_auto_open"):
                win32ext.focus_window(port, PROFILE_DIR, "?auto=1")

        threading.Thread(target=tray_job, daemon=True).start()

    def on_show():
        win32ext.focus_window(port, PROFILE_DIR)

    def on_settings():
        # 窗口已存在走 SSE；窗口刚启动则靠 URL 参数，双保险
        win32ext.focus_window(port, PROFILE_DIR, "?view=settings")
        state.publish("navigate", {"view": "settings"})

    def on_hotkey_settings():
        win32ext.focus_window(port, PROFILE_DIR, "?view=settings&focus=hotkey")
        state.publish("navigate", {"view": "settings", "focus": "hotkey"})

    def on_quit():
        state.publish("quit", {})

        def stop():
            # 必须先删托盘图标，否则进程退出后会留下关不掉的死图标
            if tray_ref["obj"]:
                tray_ref["obj"].cleanup()
                tray_ref["obj"].request_stop()
            time.sleep(0.25)
            try:
                httpd.shutdown()
            except Exception:
                pass
            os._exit(0)

        threading.Timer(0.35, stop).start()

    def on_settings_changed(cfg):
        result = {}
        if tray_ref["obj"]:
            ok = tray_ref["obj"].set_hotkey(
                int(cfg.get("hotkey_mods", 6)), int(cfg.get("hotkey_vk", 0x53)),
                str(cfg.get("hotkey") or ""))
            result["hotkey_ok"] = bool(ok)
            if not ok:
                result["hotkey_error"] = "该快捷键已被系统或其他软件占用，请换一组"
        win32ext.set_autostart(bool(cfg.get("autostart")), LAUNCH_CMD)
        state.publish("status", {"text": "设置已保存"})
        return result

    state.on_settings_changed = on_settings_changed
    state.on_quit = on_quit

    win32ext.make_icon(ICON_PATH)
    tray = win32ext.Tray(
        ICON_PATH, on_hotkey, on_show, on_settings, on_hotkey_settings, on_quit,
        int(state.cfg.get("hotkey_mods", 6)), int(state.cfg.get("hotkey_vk", 0x53)),
        str(state.cfg.get("hotkey") or "Ctrl+Shift+S"))
    tray_ref["obj"] = tray
    state.tray = tray

    if state.cfg.get("start_minimized"):
        log("启动：仅驻留托盘（不打开主窗口）")
    else:
        win32ext.focus_window(port, PROFILE_DIR)
    log("托盘与热键就绪")
    try:
        tray.run()
    finally:
        tray.stop()
    log("退出")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL\n" + traceback.format_exc())
        raise
