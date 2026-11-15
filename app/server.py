# -*- coding: utf-8 -*-
"""本地 HTTP 服务：静态 UI + JSON API + SSE 事件推送。仅监听 127.0.0.1。"""
import json
import mimetypes
import os
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config
import phonics
import services


class State:
    def __init__(self):
        self.cfg = config.load_config()
        self.subscribers = []
        self.lock = threading.Lock()
        self.tray = None
        self.vbs_path = ""
        self.on_settings_changed = None
        self.on_quit = None
        self.port = self.cfg.get("port", 21876)
        self.last_result = None       # 最近一次抓词，供新打开的窗口直接展示

    def has_subscriber(self):
        """是否有页面连着 SSE：为 False 说明主窗口已关，走托盘后台模式。"""
        with self.lock:
            return bool(self.subscribers)

    def publish(self, event, data):
        payload = "event: %s\ndata: %s\n\n" % (event, json.dumps(data, ensure_ascii=False))
        with self.lock:
            subs = list(self.subscribers)
        for q in subs:
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass

    def subscribe(self):
        q = queue.Queue(maxsize=64)
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "DuYiXia"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass

    @property
    def state(self):
        return self.server.state

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            n = 0
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # ------------------------------------------------------------ GET

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/events":
            return self._events()
        if path == "/api/state":
            return self._json({"ok": True, "config": self.state.cfg,
                               "voices": config.VOICES, "app_name": config.APP_NAME,
                               "build": config.BUILD,
                               "last_result": self.state.last_result,
                               "install_dir": config.ROOT_DIR})
        if path == "/api/history":
            return self._json({"ok": True,
                               "history": config.load_history(),
                               "favorites": config.load_favorites()})
        files = {"/": "index.html", "/index.html": "index.html",
                 "/style.css": "style.css", "/app.js": "app.js",
                 "/icon.png": "icon.png", "/favicon.ico": "icon.png"}
        name = files.get(path)
        if not name:
            return self._json({"ok": False, "error": "not found"}, 404)
        fp = os.path.join(config.WEB_DIR, name)
        try:
            with open(fp, "rb") as f:
                data = f.read()
        except OSError:
            return self._json({"ok": False, "error": "ui missing"}, 500)
        ctype = mimetypes.guess_type(name)[0] or "text/plain"
        if name.endswith((".html", ".css", ".js")):
            ctype += "; charset=utf-8"
        return self._send(200, data, ctype)

    def _events(self):
        q = self.state.subscribe()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    msg = q.get(timeout=15)
                except queue.Empty:
                    msg = ": ping\n\n"
                self.wfile.write(msg.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.state.unsubscribe(q)

    # ------------------------------------------------------------ POST

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        data = self._body()
        if path == "/api/tts":
            audio, mime, engine = services.get_tts(
                data.get("text", ""), data.get("voice") or self.state.cfg["voice"],
                self.state.cfg.get("word_voice", "dict"))
            tag = {"edge-tts 美式神经音": "edge", "快速词典发音": "fast",
                   "快速合成发音": "fast",
                   "Windows 系统语音（离线兜底）": "sapi"}.get(engine, "fail")
            return self._send(200, audio, mime, {"X-TTS-Engine": tag})
        if path == "/api/translate":
            return self._json(services.translate(data.get("text", ""), self.state.cfg))
        if path == "/api/phonics":
            word = data.get("word") or data.get("text") or ""
            info = services.lookup(word)
            result = phonics.analyze(word, info.get("usphone", ""))
            result["ukphone"] = info.get("ukphone", "")
            result["senses"] = info.get("senses", [])
            return self._json(result)
        if path == "/api/settings":
            patch = data.get("config") or {}
            old = self.state.cfg
            self.state.cfg = config.save_config(patch)
            extra = {}
            if callable(self.state.on_settings_changed):
                result = self.state.on_settings_changed(self.state.cfg)
                if isinstance(result, dict):
                    extra.update(result)
            if extra.get("hotkey_ok") is False:
                # 注册失败不要把无效组合写进配置，否则下次启动也用不了
                restore = {k: old[k] for k in ("hotkey_mods", "hotkey_vk", "hotkey")
                           if k in old}
                if restore:
                    self.state.cfg = config.save_config(restore)
            reply = {"ok": True, "config": self.state.cfg}
            reply.update(extra)
            return self._json(reply)
        if path == "/api/history":
            return self._history_action(data)
        if path == "/api/quit":
            self._json({"ok": True})
            if callable(self.state.on_quit):
                threading.Timer(0.35, self.state.on_quit).start()
            return
        return self._json({"ok": False, "error": "not found"}, 404)

    def _history_action(self, data):
        action = data.get("action", "")
        item = data.get("item") or {}
        if action == "clear":
            config.clear_history()
        elif action == "add":
            config.add_history(item, self.state.cfg.get("history_limit", 200))
        elif action == "favorite":
            added, _ = config.toggle_favorite(item)
            return self._json({"ok": True, "favorited": added})
        elif action == "unfavorite":
            config.remove_favorite(item.get("text", ""))
        return self._json({"ok": True,
                           "history": config.load_history(),
                           "favorites": config.load_favorites()})


def make_server(state, port):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.state = state
    return server
