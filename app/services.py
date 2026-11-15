# -*- coding: utf-8 -*-
"""发音、翻译、词典服务。在线美式神经音优先，断网回退 Windows 系统语音。"""
import base64
import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from collections import OrderedDict

import config  # noqa: E402
sys.path.insert(0, config.VENDOR_DIR)

CTX = ssl.create_default_context()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
_cache = OrderedDict()          # TTS 结果
_trans_cache = OrderedDict()    # 翻译结果
_lookup_cache = OrderedDict()   # 词典结果
_pending = {}                   # TTS 单次飞行：正在合成的 key -> slot
_trans_pending = {}             # 翻译单次飞行
_cache_lock = threading.RLock()
CACHE_MAX = 120
TIMEOUT = 9
WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'-]{0,31}$")


def _http(url, data=None, headers=None, timeout=TIMEOUT):
    h = dict(UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "ignore")


def _http_bytes(url, timeout=5):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read()


def _post_json(url, payload, headers=None, timeout=TIMEOUT):
    return _http(url, json.dumps(payload).encode("utf-8"),
                 {"Content-Type": "application/json", **(headers or {})}, timeout)


# ---------------------------------------------------------------- TTS

def _sapi_wav(text):
    """Windows 自带美式 SAPI 语音，纯系统能力，断网兜底。"""
    tmp = os.path.join(config.CACHE_DIR, "sapi_%s.wav" % hashlib.md5(text.encode()).hexdigest()[:10])
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    ps = (
        "$t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('%s'));"
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "try{$s.SelectVoiceByHints(0,0,0,[System.Globalization.CultureInfo]::GetCultureInfo('en-US'))}catch{};"
        "$s.SetOutputToWaveFile('%s');$s.Speak($t);$s.Dispose();" % (b64, tmp.replace("'", "''"))
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                   capture_output=True, timeout=25)
    if os.path.isfile(tmp):
        with open(tmp, "rb") as f:
            data = f.read()
        try:
            os.remove(tmp)
        except OSError:
            pass
        return data
    return b""


def _dict_voice(word):
    """有道词典美式发音 MP3：单词实测 ~0.15s，比 edge-tts 的 2s 快一个数量级。"""
    url = "https://dict.youdao.com/dictvoice?audio=" + urllib.parse.quote(word) + "&type=2"
    data = _http_bytes(url, timeout=4)
    if len(data) < 800 or not (data[:1] == b"\xff" or data[:3] == b"ID3"):
        raise RuntimeError("词典发音无数据")
    return data


def _baidu_voice(text):
    """百度网页发音接口：整句/长文本 0.4~1.4s，比 edge-tts 快 2~5 倍，支持 500 字。"""
    lan = "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en"
    url = "https://fanyi.baidu.com/gettts?" + urllib.parse.urlencode(
        {"text": text[:800], "lan": lan, "spd": 3, "source": "web"})
    data = _http_bytes(url, timeout=6)
    if len(data) < 800 or not (data[:1] == b"\xff" or data[:3] == b"ID3"):
        raise RuntimeError("快速发音无数据")
    return data


def tts(text, voice, word_voice="dict"):
    """返回 (音频字节, mime, 引擎名)。快速模式：单词走词典音，句子走百度音；失败回退 edge-tts。"""
    text = (text or "").strip()
    if not text:
        return b"", "audio/mpeg", "none"
    if len(text) > 1200:
        text = text[:1200]
    key = (text, voice, word_voice)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]

    result = None
    if word_voice != "edge":
        try:
            if WORD_RE.match(text):
                result = (_dict_voice(text), "audio/mpeg", "快速词典发音")
            elif len(text) <= 800:
                result = (_baidu_voice(text), "audio/mpeg", "快速合成发音")
        except Exception:
            result = None
    if result is None:
        try:
            import asyncio
            import edge_tts
            out = os.path.join(config.CACHE_DIR,
                               "e_%s.mp3" % hashlib.md5((text + voice).encode()).hexdigest()[:12])
            asyncio.run(edge_tts.Communicate(text, voice).save(out))
            if os.path.isfile(out):
                with open(out, "rb") as f:
                    data = f.read()
                try:
                    os.remove(out)
                except OSError:
                    pass
                if data:
                    result = (data, "audio/mpeg", "edge-tts 美式神经音")
        except Exception:
            result = None
    if result is None:
        try:
            wav = _sapi_wav(text)
            if wav:
                result = (wav, "audio/wav", "Windows 系统语音（离线兜底）")
        except Exception:
            result = None
    if result is None:
        result = (b"", "audio/mpeg", "发音失败")
    with _cache_lock:
        _cache[key] = result
        if len(_cache) > CACHE_MAX:
            _cache.popitem(last=False)
    return result


def prefetch(text, voice, word_voice="dict"):
    """抓到文字的瞬间就在后台开始合成；前端请求时直接命中结果，避免重复请求。"""
    text = (text or "").strip()[:1200]
    if not text:
        return
    key = (text, voice, word_voice)
    with _cache_lock:
        if key in _cache or key in _pending:
            return
        slot = {"event": threading.Event(), "result": None}
        _pending[key] = slot

    def job():
        try:
            slot["result"] = tts(text, voice, word_voice)
        except Exception:
            slot["result"] = (b"", "audio/mpeg", "发音失败")
        finally:
            with _cache_lock:
                _pending.pop(key, None)
            slot["event"].set()

    threading.Thread(target=job, daemon=True).start()


def get_tts(text, voice, word_voice="dict"):
    """若预热正在合成就等它完成，不重复合成同一段文字。"""
    text = (text or "").strip()[:1200]
    key = (text, voice, word_voice)
    with _cache_lock:
        slot = _pending.get(key)
    if slot:
        slot["event"].wait(timeout=8)
        return slot["result"] or tts(text, voice, word_voice)
    return tts(text, voice, word_voice)


def prefetch_all(text, cfg):
    """并行预热发音 / 翻译 / 词典，三者互不等待。"""
    prefetch(text, cfg.get("voice", "en-US-AriaNeural"), cfg.get("word_voice", "dict"))
    threading.Thread(target=lambda: translate(text, cfg), daemon=True).start()
    if WORD_RE.match((text or "").strip()):
        threading.Thread(target=lambda: lookup(text), daemon=True).start()


# ---------------------------------------------------------------- 翻译

def _detect_pair(text, target):
    han = len(re.findall(r"[\u4e00-\u9fff]", text))
    target = target.replace("zh-Hans", "zh-CN")
    if han > max(2, len(text) * 0.15):
        return "zh-CN", "en"
    return "en", target


def _mymemory(text, cfg):
    src, tgt = _detect_pair(text, cfg.get("target_lang", "zh-CN"))
    url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(
        {"q": text[:480], "langpair": src + "|" + tgt})
    d = json.loads(_http(url))
    out = d.get("responseData", {}).get("translatedText", "")
    if d.get("responseStatus") != 200 or not out or "MYMEMORY WARNING" in out:
        raise RuntimeError("MyMemory 未返回有效译文")
    return out


def _google(text, cfg):
    url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(
        {"client": "gtx", "sl": "auto", "tl": cfg.get("target_lang", "zh-CN"), "dt": "t", "q": text[:1200]})
    d = json.loads(_http(url, timeout=6))
    out = "".join(seg[0] for seg in d[0] if seg and seg[0])
    if not out:
        raise RuntimeError("Google 未返回译文")
    return out


def _custom(text, cfg):
    url = (cfg.get("custom_api_url") or "").strip()
    key = (cfg.get("custom_api_key") or "").strip()
    if not url:
        raise RuntimeError("未填写自定义接口地址")
    headers = {"Authorization": "Bearer " + key} if key else {}
    if "chat/completions" in url:
        d = json.loads(_post_json(url, {
            "model": cfg.get("custom_model", "gpt-4o-mini"),
            "messages": [{"role": "system", "content": "Translate the user text into Simplified Chinese. Output the translation only."},
                         {"role": "user", "content": text[:1200]}],
            "temperature": 0,
        }, headers))
        return d["choices"][0]["message"]["content"].strip()
    d = json.loads(_post_json(url, {"text": text[:1200], "source_lang": "auto", "target_lang": "ZH"}, headers))
    return (d.get("data") or d.get("translations", [{}])[0].get("text") or d.get("text") or "").strip()


BAIDU_LANG = {
    "zh-CN": "zh", "zh-TW": "cht", "en": "en", "ja": "jp", "ko": "kor",
    "fr": "fra", "de": "de", "es": "spa", "ru": "ru", "pt": "pt", "it": "it",
}


def _baidu(text, cfg):
    """百度翻译开放平台通用翻译 API（标准版免费，需 APPID + 密钥）。"""
    appid = (cfg.get("baidu_appid") or "").strip()
    secret = (cfg.get("baidu_secret") or "").strip()
    if not appid or not secret:
        raise RuntimeError("未配置百度翻译 APPID / 密钥")
    _, tgt = _detect_pair(text, cfg.get("target_lang", "zh-CN"))
    to = BAIDU_LANG.get(tgt, tgt)
    body = text[:2000]
    salt = str(int.from_bytes(os.urandom(4), "big"))
    sign = hashlib.md5((appid + body + salt + secret).encode("utf-8")).hexdigest()
    payload = urllib.parse.urlencode({
        "q": body, "from": "auto", "to": to,
        "appid": appid, "salt": salt, "sign": sign,
    }).encode("utf-8")
    d = json.loads(_http("https://fanyi-api.baidu.com/api/trans/vip/translate", payload,
                         {"Content-Type": "application/x-www-form-urlencoded"}, timeout=10))
    if "trans_result" not in d:
        raise RuntimeError("百度返回 %s: %s" % (d.get("error_code", "?"), d.get("error_msg", "无译文")))
    out = "\n".join(x.get("dst", "") for x in d["trans_result"]).strip()
    if not out:
        raise RuntimeError("百度未返回译文")
    return out


def translate(text, cfg):
    """带缓存 + 单次飞行的翻译入口：预热线程与页面请求共享同一次网络调用。"""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "text": "", "engine": "", "error": "文本为空", "notice": ""}
    key = (text, cfg.get("target_lang"), cfg.get("translate_engine"),
           cfg.get("baidu_appid"), cfg.get("baidu_secret"), cfg.get("custom_api_url"))
    with _cache_lock:
        if key in _trans_cache:
            _trans_cache.move_to_end(key)
            return dict(_trans_cache[key])
        slot = _trans_pending.get(key)
        owner = False
        if slot is None:
            slot = {"event": threading.Event(), "result": None}
            _trans_pending[key] = slot
            owner = True

    if owner:
        def job():
            try:
                r = _translate_uncached(text, cfg)
                with _cache_lock:
                    _trans_cache[key] = dict(r)
                    if len(_trans_cache) > CACHE_MAX:
                        _trans_cache.popitem(last=False)
                slot["result"] = r
            except Exception as exc:
                slot["result"] = {"ok": False, "text": "", "engine": "",
                                  "error": str(exc)[:80], "notice": ""}
            finally:
                with _cache_lock:
                    _trans_pending.pop(key, None)
                slot["event"].set()

        threading.Thread(target=job, daemon=True).start()

    slot["event"].wait(timeout=12)
    return dict(slot["result"] or
                 {"ok": False, "text": "", "engine": "", "error": "翻译超时", "notice": ""})


def _translate_uncached(text, cfg):
    text = (text or "").strip()
    if not text:
        return {"ok": False, "text": "", "engine": "", "error": "文本为空", "notice": ""}
    mode = cfg.get("translate_engine", "baidu")
    configured = bool((cfg.get("baidu_appid") or "").strip() and (cfg.get("baidu_secret") or "").strip())
    notice = ""
    if mode == "custom":
        order = ["custom", "mymemory"]
    elif mode == "free":
        order = ["mymemory", "google"]
    elif mode == "baidu":
        if configured:
            order = ["baidu", "mymemory", "google"]
        else:
            order = ["mymemory", "google"]
            notice = "未配置百度翻译密钥，暂用备用引擎；在设置页填 APPID 与密钥后即切换为百度翻译。"
    else:
        order = (["baidu", "mymemory", "google"] if configured
                 else ["mymemory", "google"])
        if not configured:
            notice = "未配置百度翻译密钥，暂用备用引擎；在设置页填 APPID 与密钥后即切换为百度翻译。"
    funcs = {"baidu": _baidu, "mymemory": _mymemory, "google": _google, "custom": _custom}
    labels = {"baidu": "百度翻译", "mymemory": "MyMemory", "google": "Google", "custom": "自定义接口"}
    errors = []
    for name in order:
        try:
            out = funcs[name](text, cfg)
            if out:
                return {"ok": True, "text": out, "engine": labels[name],
                        "error": "", "notice": notice}
        except Exception as e:
            errors.append("%s: %s" % (labels[name], str(e)[:90]))
    return {"ok": False, "text": "", "engine": "", "notice": notice,
            "error": " / ".join(errors) or "翻译失败"}


# ---------------------------------------------------------------- 词典

def lookup(word):
    """带缓存的词典查询。"""
    key = re.sub(r"[^A-Za-z'-]", "", (word or "").strip())[:40]
    if not key:
        return {"usphone": "", "ukphone": "", "senses": []}
    with _cache_lock:
        if key in _lookup_cache:
            _lookup_cache.move_to_end(key)
            return dict(_lookup_cache[key])
    result = _lookup_uncached(key)
    with _cache_lock:
        _lookup_cache[key] = dict(result)
        if len(_lookup_cache) > CACHE_MAX:
            _lookup_cache.popitem(last=False)
    return result


def _lookup_uncached(word):
    """有道词典公开接口：美式音标 + 常用释义。失败返回空结构。"""
    word = re.sub(r"[^A-Za-z'-]", "", (word or "").strip())[:40]
    if not word:
        return {"usphone": "", "ukphone": "", "senses": []}
    try:
        d = json.loads(_http("https://dict.youdao.com/jsonapi?q=" + urllib.parse.quote(word), timeout=7))
    except Exception:
        return {"usphone": "", "ukphone": "", "senses": []}
    simple = (d.get("simple") or {}).get("word") or [{}]
    us = (simple[0] or {}).get("usphone", "")
    uk = (simple[0] or {}).get("ukphone", "")
    senses = []
    for w in ((d.get("ec") or {}).get("word") or [])[:1]:
        for tr in (w.get("trs") or [])[:5]:
            for t in (tr.get("tr") or [])[:1]:
                val = ((t.get("l") or {}).get("i") or [])
                if isinstance(val, str):
                    val = [val]
                senses.extend([re.sub(r"<[^>]+>", "", x) for x in val if isinstance(x, str)])
    return {"usphone": us, "ukphone": uk, "senses": senses[:5]}
