# -*- coding: utf-8 -*-
"""读一下 绿色安装器：把程序安装到用户自选的任意盘符/目录。

自动识别仓库根目录是否存在已构建的 读一下.exe；存在则只复制 exe，
否则按源码模式安装（依赖本机 Python 3.10+）。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import winreg

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
EXE_NAME = "读一下.exe"
LAUNCH_VBS = "启动.vbs"
UNINSTALL_BAT = "卸载.bat"


def ask(prompt, default=""):
    try:
        v = input(prompt).strip().strip('"').strip()
    except (EOFError, KeyboardInterrupt):
        v = ""
    return v or default


def yes(question, default=False):
    v = ask(question + (" [Y/n]: " if default else " [y/N]: "), "").lower()
    return (v.startswith("y") if not default else not v.startswith("n"))


def find_python():
    p = shutil.which("python") or shutil.which("python3") or sys.executable
    p = os.path.abspath(p)
    w = os.path.join(os.path.dirname(p), "pythonw.exe")
    return w if os.path.isfile(w) else p


def write_vbs(dest, pyw):
    text = (
        "Option Explicit\n"
        "Dim fso, sh, base, py, q, cmd\n"
        'Set fso = CreateObject("Scripting.FileSystemObject")\n'
        'Set sh = CreateObject("WScript.Shell")\n'
        "base = fso.GetParentFolderName(WScript.ScriptFullName)\n"
        'py = "' + pyw.replace('"', '""') + '"\n'
        "q = Chr(34)\n"
        'cmd = q & py & q & " " & q & base & "\\app\\main.py" & q\n'
        "sh.CurrentDirectory = base\n"
        "sh.Run cmd, 0, False\n"
    )
    # WSH 默认按 ANSI 读取 .vbs，中文用户名/路径必须用 UTF-16
    with open(os.path.join(dest, LAUNCH_VBS), "w", encoding="utf-16") as f:
        f.write(text)


def make_shortcut(dest, exe_mode):
    desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    if not os.path.isdir(desktop):
        desktop = os.path.join(os.environ.get("USERPROFILE", ""), "OneDrive", "Desktop")
    if not os.path.isdir(desktop):
        return False
    lnk = os.path.join(desktop, "读一下.lnk")
    if exe_mode:
        target = os.path.join(dest, EXE_NAME)
        args, ico = "", target
    else:
        target = "wscript.exe"
        args = '"%s"' % os.path.join(dest, LAUNCH_VBS)
        ico = os.path.join(dest, "app", "icon.ico")
    ps = ("$s=New-Object -ComObject WScript.Shell;"
          "$l=$s.CreateShortcut('%s');"
          "$l.TargetPath='%s';"
          "$l.Arguments='%s';"
          "$l.WorkingDirectory='%s';"
          "$l.IconLocation='%s';"
          "$l.Description='读一下 · 划词朗读';"
          "$l.Save()" % (lnk.replace("'", "''"), target.replace("'", "''"),
                         args.replace("'", "''"), dest.replace("'", "''"),
                         ico.replace("'", "''")))
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, timeout=20)
        return os.path.isfile(lnk)
    except Exception:
        return False


def set_autostart(dest, enable, exe_mode):
    cmd = ('"%s"' % os.path.join(dest, EXE_NAME)) if exe_mode else \
          ('wscript.exe "%s"' % os.path.join(dest, LAUNCH_VBS))
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, "LingoRead")   # 清理旧版残留
        except FileNotFoundError:
            pass
        if enable:
            winreg.SetValueEx(key, "读一下", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, "读一下")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def patch_config(dest, patch):
    d = os.path.join(dest, ".duyixia")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    cfg.update(patch)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def main():
    exe_mode = os.path.isfile(os.path.join(ROOT, EXE_NAME))
    print("=" * 56)
    print("  读一下 安装  |  绿色版，可安装到任意磁盘")
    print("=" * 56)
    if exe_mode:
        print("模式：单文件 exe（自带 Python 运行时，无需安装 Python）")
        pyw = ""
    else:
        print("模式：源码版（依赖本机 Python 3.10+ 与 Microsoft Edge）")
        pyw = find_python()
        print("检测到 Python: %s" % pyw)
        print("请先执行 pip install -r requirements.txt")
        if not os.path.isfile(pyw):
            print("未找到 Python，请先安装 Python 3.10 以上版本。")
            return 1
    print()
    print("请输入安装目录（可直接输入盘符，如 E: 或 E:\\Tools\\读一下）")
    dest = ask("安装目录 [默认 D:\\读一下]: ", r"D:\读一下").replace("/", "\\")
    if re.match(r"^[A-Za-z]:$", dest):
        dest += r"\读一下"
    if not re.match(r"^[A-Za-z]:\\", dest):
        print("路径格式不正确，需要以盘符开头。")
        return 1
    if not os.path.isdir(dest[:2] + "\\"):
        print("磁盘 %s 不存在，请换一个盘符。" % (dest[:2] + "\\"))
        return 1
    dest = os.path.normpath(dest)
    if os.path.normcase(dest) == os.path.normcase(ROOT):
        print("不能安装到当前源目录，请选择其他位置。")
        return 1
    if os.path.isdir(dest) and os.listdir(dest):
        if not yes("目录已存在且非空，是否继续？", True):
            return 0

    print("\n正在复制文件到 %s ..." % dest)
    try:
        os.makedirs(dest, exist_ok=True)
        if exe_mode:
            shutil.copy2(os.path.join(ROOT, EXE_NAME), os.path.join(dest, EXE_NAME))
        else:
            subprocess.check_call([sys.executable, os.path.join(SCRIPTS, "prepare_assets.py")])
            shutil.copytree(os.path.join(ROOT, "app"), os.path.join(dest, "app"),
                            dirs_exist_ok=True)
            shutil.copy2(os.path.join(ROOT, "requirements.txt"),
                         os.path.join(dest, "requirements.txt"))
            write_vbs(dest, pyw)
        src = os.path.join(SCRIPTS, "uninstall.bat")
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dest, UNINSTALL_BAT))
    except Exception as e:
        print("复制失败：%s" % e)
        return 1

    launcher = EXE_NAME if exe_mode else LAUNCH_VBS
    if yes("创建桌面快捷方式？", True):
        print("快捷方式：%s" % ("已创建" if make_shortcut(dest, exe_mode)
                                else "创建失败（可手动运行 %s）" % launcher))
    auto = yes("设置开机自启（托盘常驻）？", False)
    set_autostart(dest, auto, exe_mode)
    if not exe_mode:
        patch_config(dest, {"autostart": auto})

    print("\n安装完成：%s" % dest)
    print("启动：双击该目录下的 %s" % launcher)
    print("热键：Ctrl+Shift+S（可在设置里改成任意组合键）")
    print("卸载：运行 %s，然后手动删除该目录" % UNINSTALL_BAT)
    print()
    if yes("现在启动 读一下？", True):
        try:
            if exe_mode:
                subprocess.Popen([os.path.join(dest, EXE_NAME)], cwd=dest)
            else:
                subprocess.Popen(["wscript.exe", os.path.join(dest, LAUNCH_VBS)])
            print("已启动，请查看任务栏托盘图标。")
        except Exception as e:
            print("启动失败：%s" % e)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:
        print("安装出错：%s" % e)
        code = 1
    if code:
        try:
            input("按回车键退出...")
        except (EOFError, KeyboardInterrupt):
            pass
    sys.exit(code)
