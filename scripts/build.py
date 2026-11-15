# -*- coding: utf-8 -*-
"""构建单文件版 读一下.exe（Windows）。

自动把运行时依赖与 PyInstaller 装进临时目录 _buildtools，产物输出到仓库根。
中间产物均为 ASCII 名，最终 exe 使用中文名。
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
BT = os.path.join(ROOT, "_buildtools")
DIST = os.path.join(ROOT, "_dist")
WORK = os.path.join(ROOT, "_buildtmp")
APP = os.path.join(ROOT, "app")


def pip_install(req_file):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet",
                           "--upgrade", "--target", BT, "-r", req_file])


def main():
    subprocess.check_call([sys.executable, os.path.join(SCRIPTS, "prepare_assets.py")])
    pip_install(os.path.join(ROOT, "requirements.txt"))
    pip_install(os.path.join(ROOT, "requirements-build.txt"))

    env = os.environ.copy()
    env["PYTHONPATH"] = BT
    hidden = ["edge_tts", "edge_playback", "aiohttp", "aiosignal", "frozenlist",
              "multidict", "propcache", "yarl", "aiohappyeyeballs", "attr",
              "attrs", "idna", "certifi", "typing_extensions"]
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--onefile", "--noconsole", "--name", "DuYiXia",
           "--icon", os.path.join(APP, "icon.ico"),
           "--distpath", DIST, "--workpath", WORK, "--specpath", WORK,
           "--paths", BT,
           "--add-data", os.path.join(APP, "web") + os.pathsep + "web",
           "--add-data", os.path.join(APP, "icon.ico") + os.pathsep + ".",
           "--collect-data", "certifi"]
    for name in hidden:
        cmd += ["--hidden-import", name]
    cmd.append(os.path.join(APP, "main.py"))
    subprocess.check_call(cmd, env=env, cwd=ROOT)

    src = os.path.join(DIST, "DuYiXia.exe")
    dst = os.path.join(ROOT, "读一下.exe")
    shutil.copy2(src, dst)
    print("OK:", dst, os.path.getsize(dst), "bytes")


if __name__ == "__main__":
    main()
