# Contributing

## 开发环境

Windows 10/11、Python 3.10+、系统自带 Edge、Node.js（仅用于 `node --check`）。

```bash
python -m pip install -r requirements.txt
python scripts/prepare_assets.py
python app/main.py
```

修改图标时，把新的 `icon.ico` / `icon.png` 转成 base64 文本覆盖 `assets/*.base64`：

```bash
python -c "import base64,pathlib; print(base64.b64encode(pathlib.Path('app/icon.ico').read_bytes()).decode())"
```

## 约定

- 后端只用 Python 标准库 + `requirements.txt` 声明的依赖；前端为原生 HTML/CSS/JS，不引入框架。
- 提交前跑 `python -m py_compile app/*.py scripts/*.py` 与 `node --check app/web/app.js`。
- CI 配置模板在 `ci/syntax-check.yml`；需要 GitHub Actions 时把它复制到 `.github/workflows/`（该操作要求 token 具备 `workflow` scope）。
- 不要把 `.duyixia/`、`*.exe`、`*.zip`、`python_path.txt` 或本机绝对路径提交进仓库。
- 运行时数据一律写入 `.duyixia`，保持解压目录干净。
- 新增在线服务时，请在 README 的「依赖与许可证」与隐私说明里同步列出。

欢迎提交 issue 与 pull request。
