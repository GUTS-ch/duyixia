# -*- coding: utf-8 -*-
"""从 assets/*.base64 还原二进制图标。

仓库以纯文本保存图标，避免二进制文件混入 Git；克隆后运行本脚本即可
生成 app/icon.ico（托盘 / exe 图标）与 app/web/icon.png（网页图标）。
build.py 与 install.py 会自动调用。
"""
import base64
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = (
    ("icon.ico.base64", os.path.join("app", "icon.ico")),
    ("icon.png.base64", os.path.join("app", "web", "icon.png")),
)


def restore():
    for name, rel in TARGETS:
        src = os.path.join(ROOT, "assets", name)
        with open(src, "r", encoding="ascii") as f:
            raw = base64.b64decode("".join(f.read().split()))
        out = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.isfile(out):
            with open(out, "rb") as f:
                if f.read() == raw:
                    continue
        with open(out, "wb") as f:
            f.write(raw)
        print("restored %s (%d bytes)" % (rel, len(raw)))


if __name__ == "__main__":
    restore()
