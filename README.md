# 读一下 · DuYiXia

> 在任意软件里选中英文，按一个键，立刻听到美式发音、看到中文译文；单词还会给出音标与**自然拼读拆解**。

一款 Windows 上的轻量划词朗读工具。绿色免安装、托盘常驻、单文件 exe 约 10 MB，界面参考欧路词典。

## 功能

- **全局热键抓词**：选中文字后按 `Ctrl+Shift+S`（可自定义），自动朗读 + 翻译 + 记入历史
- **分级发音**：单词走词典真人发音（实测约 0.14 秒出声），句子走网页发音接口（约 0.6–0.9 秒），失败依次回退 edge-tts 美式神经音、Windows 系统语音（离线）
- **联网翻译**：百度翻译开放平台（需 APPID/密钥）／MyMemory 免 Key／自定义 OpenAI 兼容或 DeepLX 风格接口
- **自然拼读**：本地规则引擎，音节切分 + 字母组合逐块（IPA、近似音、规则、例词），点击拼读块朗读例词
- **词典信息**：美/英音标与常用中文释义
- **托盘后台**：关掉主窗口后按热键仍能朗读，译文用系统通知显示，不打断操作
- **其他**：生词本、历史记录、开机自启、深色主题、可录制快捷键

## 运行环境

| 项 | 要求 |
|---|---|
| 系统 | Windows 10 / 11 x64 |
| 界面 | 系统自带 Microsoft Edge（用作无边框窗口；仅界面，托盘后台朗读不依赖它） |
| Python | 源码运行需 3.10+；单文件 exe 自带运行时 |
| 网络 | 发音、翻译、音标需联网；断网时自动回退 Windows 系统语音 |
| 本机服务 | 仅监听 `127.0.0.1:21876`，不对外、无账号、无遥测 |

## 快速开始

**下载**：[Releases · v1.0.0](https://github.com/GUTS-ch/duyixia/releases/tag/v1.0.0) 提供免安装包 `DuYiXia-Portable-v1.0.0.zip`，解压后双击 `读一下.exe` 即用。

本仓库只保存源码（不提交编译产物）；也可按下面的「构建单文件 exe」自行生成。

```bash
git clone https://github.com/GUTS-ch/duyixia.git
cd duyixia
python -m pip install -r requirements.txt
python scripts/prepare_assets.py        # 还原 app/icon.ico 与 app/web/icon.png
python app/main.py                      # 或双击 scripts/run_source.bat（无黑窗）
```

构建单文件 exe（自动安装 PyInstaller 与依赖，约 1–3 分钟）：

```bash
python scripts/build.py                 # 产物：仓库根目录下 读一下.exe
```

把 exe 复制到任意盘任意目录双击即可；也可运行 `scripts/install.bat` 自选目录安装并创建快捷方式。

## 使用方法

1. 在浏览器、PDF、Word 等**可选中文本**的窗口里选中英文 → 按 `Ctrl+Shift+S`。
2. 主界面也可直接在顶部搜索框输入英文，回车查询。
3. **托盘左键**呼出主窗口；**右键**菜单：显示主窗口 / 设置 / 设置快捷键… / 退出 读一下。
4. 左侧五个页签：朗读、拼读、历史、生词本、设置。星标加入生词本；点拼读块听规则例词。

**设置要点**

- 触发热键支持录制任意组合键，立即生效；被占用会提示并自动回滚。
- 翻译默认百度，需填 APPID + 密钥（标准版免费，注册地址在设置页）；**不填也能用**，会自动回退免 Key 引擎并提示。
- 4 个美式音色只在「统一美式神经音」模式或快速通道失败回退时生效；快速模式使用固定发音接口。

配置、历史、生词本、缓存、日志全部写在 exe（或仓库根）同目录的隐藏目录 `.duyixia`，已加入 `.gitignore`。

## 项目结构

```
app/
  main.py        入口：本地服务 + 托盘 + 全局热键
  server.py      HTTP API 与 SSE 事件推送（仅 127.0.0.1）
  services.py    发音 / 翻译 / 词典，含缓存与并行预热
  phonics.py     自然拼读规则引擎（纯标准库）
  win32ext.py    Win32 剪贴板、托盘、热键、窗口置前、音频播放
  config.py      配置与本地数据持久化
  web/           欧路词典风格的 HTML / CSS / JS 界面
scripts/         构建、安装、卸载、资源还原脚本
ci/              GitHub Actions 配置模板（可选启用）
assets/          图标（base64 文本形式，见下）
```

图标以 `assets/*.base64` 文本保存，克隆后由 `scripts/prepare_assets.py` 还原为 `app/icon.ico` 与 `app/web/icon.png`；这样仓库里没有二进制文件，也便于纯 API 提交。

## 依赖与许可证

本项目采用 [MIT](LICENSE)。第三方依赖：

| 依赖 | 许可证 | 用途 |
|---|---|---|
| [edge-tts](https://github.com/rany2/edge-tts) | LGPL-3.0 | 美式神经音（回退通道） |
| aiohttp 及其依赖 | Apache-2.0 等 | edge-tts 的传输层 |
| certifi | MPL-2.0 | CA 证书 |
| PyInstaller | GPL-2.0 with exception | 仅构建期使用，不随源码分发 |

**分发预编译 exe 时**，其中打包了上述第三方库，请一并遵守各自许可证（尤其是 LGPL-3.0 关于可替换该库的要求）。

发音与翻译依赖第三方在线服务：有道词典（发音/音标/释义）、百度网页发音接口、百度翻译开放平台、MyMemory、Google（备用）、微软在线语音（edge-tts），或你填写的自定义接口。**选中的文本会发送给这些服务**；除此之外不上传任何数据，无遥测、无账号。

## 已知限制

- 自然拼读是规则表推导，不是词典级逐词 IPA；`colonel` 等不规则词会按常规规则拆，句子不拆解。
- 图片、游戏内画面、禁止模拟 `Ctrl+C` 的软件无法抓词；一次最多取 3000 字符。
- 百度网页免 Key 翻译接口有风控，稳定可用的是开放平台 API；Google 在国内通常不可达。免 Key 备用引擎（MyMemory / Google）在部分网络下会直接超时，**建议配置百度 APPID + 密钥**以获得稳定译文。
- 快捷键若被浏览器或系统截获，录制时页面收不到按键，换一组即可。
- 打包的 exe 可能被杀软误报（PyInstaller 单文件常见），加信任即可。

详见 [CHANGELOG.md](CHANGELOG.md) 与 [CONTRIBUTING.md](CONTRIBUTING.md)。
