# -*- coding: utf-8 -*-
"""Windows 原生集成：剪贴板、全局热键、系统托盘、开机自启、无边框窗口。纯 ctypes，零第三方依赖。"""
import ctypes
import ctypes.wintypes as w
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
import winreg

c_size_t = ctypes.c_size_t
c_ssize_t = ctypes.c_ssize_t
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
winmm = ctypes.WinDLL("winmm")
winmm.mciSendStringW.argtypes = [w.LPCWSTR, w.LPWSTR, w.UINT, w.HWND]
winmm.mciSendStringW.restype = w.DWORD
_play_lock = threading.Lock()

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
VK_CONTROL, VK_SHIFT, VK_MENU, VK_C = 0x11, 0x10, 0x12, 0x43
VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002
WM_HOTKEY, WM_DESTROY, WM_COMMAND, WM_APP = 0x0312, 0x0002, 0x0111, 0x8000
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_LBUTTONDBLCLK = 0x0201, 0x0202, 0x0203
WM_RBUTTONDOWN, WM_RBUTTONUP = 0x0204, 0x0205
WM_CONTEXTMENU, WM_NULL = 0x007B, 0x0000
NIN_SELECT, NIN_KEYSELECT = 0x0400, 0x0401
NIM_ADD, NIM_MODIFY, NIM_DELETE, NIM_SETVERSION = 0, 1, 2, 4
NOTIFYICON_VERSION_4 = 4
# 注意：NIF_MESSAGE=0x1 / NIF_ICON=0x2 / NIF_TIP=0x4（曾把 NIF_MESSAGE 误写成 0x4，
# 导致 uCallbackMessage 从未生效，托盘点击完全收不到通知）
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x0001, 0x0002, 0x0004
NIF_STATE, NIF_INFO, NIF_GUID = 0x0008, 0x0010, 0x0020
TPM_RETURNCMD, TPM_RIGHTALIGN, TPM_NONOTIFY = 0x0100, 0x0008, 0x0080
MF_SEPARATOR = 0x0800
SW_SHOW, SW_RESTORE = 5, 9
WS_EX_TOOLWINDOW, WS_POPUP = 0x00000080, 0x80000000

user32.OpenClipboard.argtypes = [w.HWND]
user32.OpenClipboard.restype = w.BOOL
user32.CloseClipboard.restype = w.BOOL
user32.EmptyClipboard.restype = w.BOOL
user32.GetClipboardData.argtypes = [w.UINT]
user32.GetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [w.UINT, ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [w.UINT, c_size_t]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
kernel32.GetModuleHandleW.argtypes = [w.LPCWSTR]
kernel32.GetModuleHandleW.restype = w.HMODULE
user32.keybd_event.argtypes = [w.BYTE, w.BYTE, w.DWORD, c_size_t]
user32.RegisterHotKey.argtypes = [w.HWND, ctypes.c_int, w.UINT, w.UINT]
user32.UnregisterHotKey.argtypes = [w.HWND, ctypes.c_int]
user32.PostMessageW.argtypes = [w.HWND, w.UINT, c_size_t, c_ssize_t]
user32.SendMessageW.argtypes = [w.HWND, w.UINT, c_size_t, c_ssize_t]
user32.SendMessageW.restype = c_ssize_t
user32.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, c_size_t, c_ssize_t,
                                       w.UINT, w.UINT, ctypes.POINTER(c_ssize_t)]
user32.SendMessageTimeoutW.restype = c_ssize_t
user32.SetForegroundWindow.argtypes = [w.HWND]
user32.GetForegroundWindow.restype = w.HWND
user32.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
user32.BringWindowToTop.argtypes = [w.HWND]
user32.SwitchToThisWindow.argtypes = [w.HWND, w.BOOL]
user32.IsIconic.argtypes = [w.HWND]
user32.FlashWindow.argtypes = [w.HWND, w.BOOL]
user32.SetWindowPos.argtypes = [w.HWND, c_ssize_t, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, w.UINT]
user32.AttachThreadInput.argtypes = [w.DWORD, w.DWORD, w.BOOL]
user32.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
kernel32.GetCurrentThreadId.restype = w.DWORD
user32.DestroyWindow.argtypes = [w.HWND]
user32.IsWindowVisible.argtypes = [w.HWND]
user32.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user32.EnumWindows.argtypes = [ctypes.c_void_p, c_ssize_t]
user32.GetCursorPos.argtypes = [ctypes.POINTER(w.POINT)]
user32.CreatePopupMenu.restype = w.HMENU
user32.AppendMenuW.argtypes = [w.HMENU, w.UINT, c_size_t, w.LPCWSTR]
user32.TrackPopupMenu.argtypes = [w.HMENU, w.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, ctypes.c_void_p]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.DestroyMenu.argtypes = [w.HMENU]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.LoadImageW.argtypes = [w.HINSTANCE, w.LPCWSTR, w.UINT, ctypes.c_int, ctypes.c_int, w.UINT]
user32.LoadImageW.restype = w.HANDLE
user32.DefWindowProcW.argtypes = [w.HWND, w.UINT, c_size_t, c_ssize_t]
user32.DefWindowProcW.restype = c_ssize_t
shell32.Shell_NotifyIconW.argtypes = [w.DWORD, ctypes.c_void_p]
shell32.Shell_NotifyIconW.restype = w.BOOL


# ---------------------------------------------------------------- 日志 / 窗口置前

def log_line(text):
    try:
        import config
        with open(os.path.join(config.RUNTIME_DIR, "app.log"), "a",
                  encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), text))
    except Exception:
        pass


def force_foreground(hwnd):
    """Windows 前台锁定会拒绝后台进程的 SetForegroundWindow（托盘点击「没反应」的根因）。

    依次用 AttachThreadInput、ALT 敲击、SwitchToThisWindow 三种方式绕过。
    """
    if not hwnd:
        return False
    fg = user32.GetForegroundWindow()
    cur = kernel32.GetCurrentThreadId()
    pid = w.DWORD()
    fg_tid = user32.GetWindowThreadProcessId(fg, ctypes.byref(pid)) if fg else 0
    attached = False
    if fg_tid and fg_tid != cur:
        attached = bool(user32.AttachThreadInput(cur, fg_tid, True))
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    else:
        user32.ShowWindow(hwnd, SW_SHOW)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    if attached:
        user32.AttachThreadInput(cur, fg_tid, False)
    if user32.GetForegroundWindow() != hwnd:
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    if user32.GetForegroundWindow() != hwnd:
        try:
            user32.SwitchToThisWindow(hwnd, True)
        except Exception:
            pass
    ok = user32.GetForegroundWindow() == hwnd
    if not ok:
        # 最后兜底：临时置顶，确保窗口一定出现在屏幕上，1.2s 后取消
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
        user32.FlashWindow(hwnd, True)

        def _undo_topmost():
            time.sleep(1.2)
            try:
                user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0,
                                    0x0001 | 0x0002 | 0x0010)
            except Exception:
                pass

        threading.Thread(target=_undo_topmost, daemon=True).start()
    return ok


# ---------------------------------------------------------------- 剪贴板

def get_clipboard_text():
    if not user32.OpenClipboard(None):
        return ""
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        if not p:
            return ""
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def set_clipboard_text(text):
    buf = ctypes.create_unicode_buffer(text or "")
    size = ctypes.sizeof(buf)
    h = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
    if not h:
        return False
    p = kernel32.GlobalLock(h)
    ctypes.memmove(p, buf, size)
    kernel32.GlobalUnlock(h)
    if not user32.OpenClipboard(None):
        kernel32.GlobalFree(h)
        return False
    user32.EmptyClipboard()
    user32.SetClipboardData(CF_UNICODETEXT, h)
    user32.CloseClipboard()
    return True


def send_ctrl_c():
    """模拟 Ctrl+C 抓取当前选中文本。先松开可能按住的修饰键，避免热键冲突。"""
    for vk in (VK_SHIFT, VK_MENU):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def grab_selection(max_wait=0.28):
    """Ctrl+C 抓词：轮询代替固定 0.2s 等待，通常 0.02~0.06s 就能拿到文本。"""
    old = get_clipboard_text()
    set_clipboard_text("")
    send_ctrl_c()
    text = ""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        text = get_clipboard_text().strip()
        if text:
            break
        time.sleep(0.02)
    set_clipboard_text(old)
    return text


def play_audio(data, mime="audio/mpeg", cache_dir=None):
    """不依赖浏览器页面，直接用 winmm 播放音频：主窗口关到托盘后也能朗读。"""
    if not data:
        return False
    ext = ".wav" if "wav" in (mime or "") else ".mp3"
    path = os.path.join(cache_dir or os.environ.get("TEMP", "."), "lrvoice" + ext)
    kind = "waveaudio" if ext == ".wav" else "mpegvideo"
    with _play_lock:
        try:
            winmm.mciSendStringW("close lrvoice", None, 0, None)   # 打断上一段
            with open(path, "wb") as f:
                f.write(data)
            if winmm.mciSendStringW('open "%s" type %s alias lrvoice' % (path, kind),
                                   None, 0, None) != 0:
                return False
            return winmm.mciSendStringW("play lrvoice", None, 0, None) == 0
        except Exception:
            return False


# ---------------------------------------------------------------- 图标

def make_icon(path):
    """优先使用随包的「读一下.ico」；缺失时才生成简易蓝色图标。"""
    if os.path.isfile(path) and os.path.getsize(path) > 100:
        return path
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if os.path.isfile(src):
        try:
            shutil.copy2(src, path)
            return path
        except OSError:
            pass
    W = H = 32
    px = [[(0, 0, 0, 0) for _ in range(W)] for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if ((x - 15.5) ** 2 + (y - 15.5) ** 2) ** 0.5 <= 15.2:
                px[y][x] = (237, 111, 47, 255)  # BGRA -> #2F6FED
    glyph = ["0110", "1001", "1001", "1111", "1001", "1001", "1001"]
    scale, ox, oy = 3, 10, 5
    for gy, row in enumerate(glyph):
        for gx, bit in enumerate(row):
            if bit == "1":
                for dy in range(scale):
                    for dx in range(scale):
                        xx, yy = ox + gx * scale + dx, oy + gy * scale + dy
                        if 0 <= xx < W and 0 <= yy < H:
                            px[yy][xx] = (255, 255, 255, 255)
    xor = bytearray()
    for y in range(H - 1, -1, -1):
        for x in range(W):
            b, g, r, a = px[y][x]
            xor += bytes((b, g, r, a))
    image = struct.pack("<IiiHHIIiiII", 40, W, H * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    image += bytes(xor) + b"\x00" * (W * H // 8)
    ico = struct.pack("<HHH", 0, 1, 1)
    ico += struct.pack("<BBBBHHII", W, H, 0, 0, 1, 32, len(image), 22)
    ico += image
    with open(path, "wb") as f:
        f.write(ico)
    return path


# ---------------------------------------------------------------- 托盘 + 热键

WNDPROC = ctypes.WINFUNCTYPE(c_ssize_t, w.HWND, w.UINT, c_size_t, c_ssize_t)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", w.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
                ("hCursor", w.HANDLE), ("hbrBackground", w.HBRUSH),
                ("lpszMenuName", w.LPCWSTR), ("lpszClassName", w.LPCWSTR)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", w.DWORD), ("Data2", w.WORD), ("Data3", w.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT),
                ("uFlags", w.UINT), ("uCallbackMessage", w.UINT), ("hIcon", w.HICON),
                ("szTip", w.WCHAR * 128), ("dwState", w.DWORD), ("dwStateMask", w.DWORD),
                ("szInfo", w.WCHAR * 256), ("uVersion", w.UINT),
                ("szInfoTitle", w.WCHAR * 64), ("dwInfoFlags", w.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", w.HICON)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", w.HWND), ("message", w.UINT), ("wParam", c_size_t),
                ("lParam", c_ssize_t), ("time", w.DWORD), ("pt", w.POINT),
                ("lPrivate", w.DWORD)]


shell32.Shell_NotifyIconW.argtypes = [w.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]


user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   w.HWND, w.HMENU, w.HINSTANCE, ctypes.c_void_p]
user32.CreateWindowExW.restype = w.HWND
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), w.HWND, w.UINT, w.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DestroyWindow.argtypes = [w.HWND]


class Tray:
    def __init__(self, icon_path, on_hotkey, on_show, on_settings,
                 on_hotkey_settings, on_quit, mods, vk,
                 hotkey_label="Ctrl+Shift+S"):
        self.cb_hotkey = on_hotkey
        self.cb_show = on_show
        self.cb_settings = on_settings
        self.cb_hotkey_settings = on_hotkey_settings
        self.cb_quit = on_quit
        self.mods, self.vk = mods, vk
        self.hotkey_label = hotkey_label or "Ctrl+Shift+S"
        self.hwnd = None
        self.icon_path = icon_path
        self._wndproc = WNDPROC(self._proc)  # 防止被 GC
        self._nid = None
        self._running = False
        self._last_show = 0.0
        self._last_menu = 0.0
        self._last_raw_log = 0.0
        self._init_window()
        self._init_icon()

    @staticmethod
    def _safe(fn, *args):
        """窗口过程里抛出的 Python 异常会被 ctypes 静默吞掉，必须显式兜底。"""
        try:
            return fn(*args)
        except Exception as exc:
            log_line("[tray] %s: %s" % (type(exc).__name__, exc))
            return None

    def _init_window(self):
        hinst = kernel32.GetModuleHandleW(None)
        cls = WNDCLASSW()
        cls.lpfnWndProc = self._wndproc
        cls.hInstance = hinst
        cls.lpszClassName = "DuYiXiaTrayWnd"
        user32.RegisterClassW(ctypes.byref(cls))
        self.hwnd = user32.CreateWindowExW(
            0, "DuYiXiaTrayWnd", "读一下", 0, 0, 0, 0, 0,
            None, None, hinst, None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        user32.RegisterHotKey(self.hwnd, 1, self.mods | 0x4000, self.vk)

    def _init_icon(self):
        hicon = user32.LoadImageW(None, self.icon_path, 1, 32, 32, 0x0010)
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_APP + 1
        nid.hIcon = hicon
        nid.szTip = self._tip()
        nid.uVersion = 0                    # 不调用 NIM_SETVERSION：Win11 下会让回调失效
        self._nid = nid
        added = shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        log_line("[tray] NIM_ADD=%s hwnd=%s flags=0x%x callback=0x%x"
                 % (bool(added), self.hwnd, nid.uFlags, WM_APP + 1))

    def _tip(self):
        return "读一下 · 选中文字按 %s 朗读" % self.hotkey_label

    def set_tip(self, label):
        self.hotkey_label = label or self.hotkey_label
        if self._nid is not None:
            self._nid.uFlags = NIF_MESSAGE | NIF_TIP   # 保持回调消息，别只写 NIF_TIP
            self._nid.szTip = self._tip()
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def balloon(self, title, text):
        """托盘通知气泡：窗口关到托盘后用它显示译文，不依赖浏览器页面。"""
        if self._nid is None:
            return False
        try:
            nid = self._nid
            nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_INFO
            nid.szInfoTitle = (title or "读一下")[:63]
            nid.szInfo = (text or "")[:255]
            nid.dwInfoFlags = 0x0001                   # NIIF_INFO
            return bool(shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid)))
        except Exception:
            return False

    def _menu_owner(self):
        """屏幕外 1x1 工具窗口：给弹出菜单一个可见 owner，菜单才不会弹不出或立刻消失。"""
        hinst = kernel32.GetModuleHandleW(None)
        return user32.CreateWindowExW(
            WS_EX_TOOLWINDOW, "Static", "", WS_POPUP,
            -32000, -32000, 1, 1, None, None, hinst, None)

    def _menu(self):
        now = time.time()
        if now - self._last_menu < 0.35:      # V4 下右键会同时来两条消息，去重
            return
        self._last_menu = now
        menu = user32.CreatePopupMenu()
        items = [(1001, "显示主窗口"), (1002, "设置"), (1003, "设置快捷键…"),
                 (0, ""), (1004, "退出 读一下")]
        for cmd, label in items:
            if cmd == 0:
                user32.AppendMenuW(menu, MF_SEPARATOR, 0, "")
            else:
                user32.AppendMenuW(menu, 0, cmd, label)
        pt = w.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        owner = self._menu_owner() or self.hwnd
        user32.ShowWindow(owner, SW_SHOW)
        force_foreground(owner)
        cmd = user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_RIGHTALIGN | TPM_NONOTIFY,
                                    pt.x, pt.y, 0, owner, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        if owner != self.hwnd:
            user32.DestroyWindow(owner)
        log_line("[tray] menu cmd=%s" % cmd)
        if cmd == 1001:
            self._safe(self.cb_show)
        elif cmd == 1002:
            self._safe(self.cb_settings)
        elif cmd == 1003:
            self._safe(self.cb_hotkey_settings)
        elif cmd == 1004:
            self._safe(self.cb_quit)

    def _show(self):
        now = time.time()
        if now - self._last_show < 0.30:      # 双击会连发 SELECT + LBUTTONUP
            return
        self._last_show = now
        log_line("[tray] show requested")
        self._safe(self.cb_show)

    def _proc(self, hwnd, msg, wparam, lparam):
        # 诊断：把托盘窗口收到的鼠标 / 通知类消息原样记下来（0.15s 限流）
        if ((0x0200 <= msg <= 0x0210) or (0x0400 <= msg <= 0x0410)
                or msg in (WM_APP + 1, WM_APP + 2, WM_CONTEXTMENU, WM_HOTKEY)):
            now = time.time()
            if now - self._last_raw_log > 0.15:
                self._last_raw_log = now
                log_line("[wnd] raw msg=0x%x wp=0x%x lp=0x%x"
                         % (msg, wparam, lparam & 0xFFFFFFFF))
        if msg == WM_HOTKEY:
            self._safe(self.cb_hotkey)
            return 0
        if msg == WM_APP + 1:                # 托盘回调消息（V4 / V0 都兼容）
            ev = lparam & 0xFFFF
            log_line("[tray] callback ev=0x%x lp=0x%x" % (ev, lparam & 0xFFFFFFFF))
            if ev in (NIN_SELECT, NIN_KEYSELECT, WM_LBUTTONDOWN,
                      WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self._show()
            elif ev in (WM_RBUTTONDOWN, WM_RBUTTONUP, WM_CONTEXTMENU):
                self._safe(self._menu)
            return 0
        if msg == WM_CONTEXTMENU:            # Win10/11 右键通常走这条
            log_line("[tray] WM_CONTEXTMENU")
            self._safe(self._menu)
            return 0
        if msg in (WM_LBUTTONDOWN, WM_LBUTTONUP, WM_LBUTTONDBLCLK):
            log_line("[tray] direct msg=0x%x" % msg)
            self._show()
            return 0
        if msg in (WM_RBUTTONDOWN, WM_RBUTTONUP):
            log_line("[tray] direct msg=0x%x" % msg)
            self._safe(self._menu)
            return 0
        if msg == WM_APP + 2:                # 重新注册热键，同步返回结果
            new_mods, new_vk = wparam, lparam
            user32.UnregisterHotKey(self.hwnd, 1)
            ok = user32.RegisterHotKey(self.hwnd, 1, new_mods | 0x4000, new_vk)
            if ok:
                self.mods, self.vk = new_mods, new_vk
            else:                            # 被占用：恢复原来的，避免热键彻底丢失
                user32.RegisterHotKey(self.hwnd, 1, self.mods | 0x4000, self.vk)
            return 1 if ok else 0
        if msg == WM_COMMAND:
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def set_hotkey(self, mods, vk, label=None):
        """同步注册；返回 True/False，供设置页提示「快捷键被占用」。"""
        if not self.hwnd:
            return False
        result = c_ssize_t(0)
        sent = user32.SendMessageTimeoutW(self.hwnd, WM_APP + 2, mods, vk,
                                          0x0002, 2000, ctypes.byref(result))
        ok = bool(sent) and bool(result.value)
        if ok and label:
            self._safe(self.set_tip, label)
        return ok

    def request_stop(self):
        user32.PostMessageW(self.hwnd, WM_DESTROY, 0, 0)

    def cleanup(self):
        """立即移除托盘图标并注销热键。退出前必须调用，否则留下关不掉的死图标。"""
        if self._nid is not None:
            try:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            except Exception:
                pass
            self._nid = None
        if self.hwnd:
            try:
                user32.UnregisterHotKey(self.hwnd, 1)
            except Exception:
                pass

    def run(self):
        self._running = True
        m = MSG()
        try:
            while self._running:
                r = user32.GetMessageW(ctypes.byref(m), None, 0, 0)
                if r in (0, -1):
                    break
                user32.TranslateMessage(ctypes.byref(m))
                user32.DispatchMessageW(ctypes.byref(m))
        finally:
            self.cleanup()

    def stop(self):
        self.cleanup()
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        self._running = False


# ---------------------------------------------------------------- 启动 / 自启 / 窗口

def find_edge():
    candidates = [
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return "msedge.exe"


def _bundle_icon():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for p in (os.path.join(base, "icon.ico"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")):
        if os.path.isfile(p):
            return p
    return None


def _set_window_icon_async(icon_path):
    """Chromium --app 窗口用默认地球图标；等窗口出现后替换成大/小图标（标题栏 + 任务栏）。"""
    if not icon_path:
        return

    def job():
        small = user32.LoadImageW(None, icon_path, 1, 16, 16, 0x0010)
        big = user32.LoadImageW(None, icon_path, 1, 64, 64, 0x0010)
        if not small and not big:
            return
        for _ in range(10):
            time.sleep(0.5)
            hwnd = _find_app_window()
            if not hwnd:
                continue
            for _rep in range(3):        # Chromium 页面加载后可能重设图标，重复几次
                for kind, handle in ((0, small), (1, big)):
                    if handle:
                        out = c_ssize_t(0)
                        user32.SendMessageTimeoutW(hwnd, 0x0080, kind, handle,
                                                   0x0002, 500, ctypes.byref(out))
                time.sleep(0.6)
            return

    threading.Thread(target=job, daemon=True).start()


def open_window(port, profile_dir, query=""):
    edge = find_edge()
    qs = (query or "").lstrip("?")
    parts = ([qs] if qs else []) + ["_t=%d" % int(time.time() * 1000)]
    url = "http://127.0.0.1:%d/?%s" % (port, "&".join(parts))
    # 唯一 query + --new-window：避免 Edge 把同源 app 复用成「什么都不做」
    args = [edge, "--app=" + url, "--new-window", "--window-size=980,700", "--no-first-run",
            "--disable-features=msEdgeSplitScreen,msWebOOUI,msPdfOOUI",
            "--user-data-dir=" + profile_dir]
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=0x08000000)
        _set_window_icon_async(_bundle_icon())
        return True
    except Exception:
        return False


def _find_app_window():
    """找到已打开的「读一下」Chromium app 窗口，避免每次点击都新开一个进程。"""
    hits = []
    proc_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, c_ssize_t)

    def _cb(hwnd, _unused):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, 256)
        if "读一下" in title.value:
            cls = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, cls, 128)
            if cls.value.startswith("Chrome_WidgetWin"):
                hits.append(hwnd)
        return True

    proc = proc_type(_cb)
    user32.EnumWindows(ctypes.cast(proc, ctypes.c_void_p), 0)
    return hits[0] if hits else None


def focus_window(port, profile_dir, query=""):
    """左键托盘：有窗口就强制恢复并置前，没有才新开。"""
    hwnd = _find_app_window()
    if hwnd:
        ok = force_foreground(hwnd)
        log_line("[tray] focus existing hwnd=%s ok=%s" % (hwnd, ok))
        return True
    log_line("[tray] no window found, launching")
    return open_window(port, profile_dir, query)


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "读一下"
_MUTEX_HANDLE = None


def set_autostart(enable, command):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, "LingoRead")   # 清理旧版本残留项
        except FileNotFoundError:
            pass
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def single_instance():
    """进程互斥。已有实例时返回 False，避免重复启动产生多个托盘图标。"""
    global _MUTEX_HANDLE
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, w.BOOL, w.LPCWSTR]
    kernel32.CreateMutexW.restype = w.HANDLE
    _MUTEX_HANDLE = kernel32.CreateMutexW(None, False, "DuYiXia_Singleton")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def stop_legacy_instance(port):
    """若后台还跑着旧版，先通过本地接口请它优雅退出，避免新版被单实例互斥挡住。

    旧版 /api/state 没有 build 字段；同版本的新版直接跳过，不影响正常二次启动。
    """
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/api/state" % port, timeout=0.8) as r:
            info = json.loads(r.read().decode("utf-8", "ignore"))
        if int(info.get("build", 0)) >= 5:
            return False
        urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:%d/api/quit" % port, data=b"{}",
            headers={"Content-Type": "application/json"}), timeout=0.8).read()
        time.sleep(0.9)                    # 等旧进程删托盘图标、释放互斥体与端口
        return True
    except Exception:
        return False


def kill_legacy():
    """结束旧版 LingoRead.exe 残留进程（其托盘图标点不动），替代外部清理脚本。"""
    if os.path.basename(sys.executable).lower() == "lingoread.exe":
        return False                      # 用户把新版改名了，别把自己杀掉
    try:
        subprocess.run(["taskkill", "/f", "/im", "LingoRead.exe"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=0x08000000, timeout=5)
        return True
    except Exception:
        return False


def refresh_tray_icons():
    """向任务栏通知区投递鼠标移动，促使 Explorer 清掉旧进程留下的死图标。"""
    try:
        user32.FindWindowW.argtypes = [w.LPCWSTR, w.LPCWSTR]
        user32.FindWindowW.restype = w.HWND
        tray = user32.FindWindowW("Shell_TrayWnd", None)
        if not tray:
            return False
        proc_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, c_ssize_t)
        user32.EnumChildWindows.argtypes = [w.HWND, ctypes.c_void_p, c_ssize_t]

        def _cb(hwnd, _unused):
            user32.PostMessageW(hwnd, 0x0200, 0, 0)  # WM_MOUSEMOVE
            return True

        proc = proc_type(_cb)
        user32.EnumChildWindows(tray, ctypes.cast(proc, ctypes.c_void_p), 0)
        return True
    except Exception:
        return False
