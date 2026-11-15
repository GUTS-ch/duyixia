# -*- coding: utf-8 -*-
"""自然拼读(Phonics)解析引擎：字母组合切分 + 发音规则 + 音节划分。纯规则表，零依赖。"""
import re

# (IPA, 中文近似音, 规则说明, 例词)
G3 = {
    "igh": ("/aɪ/", "艾", "三字母组合 igh 发长音 /aɪ/，gh 不发音", "night"),
    "tch": ("/tʃ/", "赤", "短元音后用 tch 表示 /tʃ/", "catch"),
    "dge": ("/dʒ/", "吉", "短元音后用 dge 表示 /dʒ/", "bridge"),
    "eau": ("/oʊ/", "欧", "eau 组合常发 /oʊ/", "beautiful"),
    "air": ("/er/", "艾尔", "air 组合发 /er/，受 r 影响", "chair"),
    "are": ("/er/", "艾尔", "are 组合发 /er/", "care"),
    "ear": ("/ɪr/", "伊尔", "ear 常发 /ɪr/（也有 /er/，如 bear）", "hear"),
    "eer": ("/ɪr/", "伊尔", "eer 组合发 /ɪr/", "deer"),
    "ere": ("/ɪr/", "伊尔", "ere 组合常发 /ɪr/", "here"),
    "ire": ("/aɪr/", "艾尔", "ire 组合发 /aɪr/（Magic E + r）", "fire"),
    "ore": ("/ɔr/", "奥尔", "ore 组合发 /ɔr/", "more"),
    "ure": ("/jʊr/", "尤尔", "ure 组合发 /jʊr/", "cure"),
    "our": ("/aʊr/", "奥尔", "our 常发 /aʊr/（如 four 读 /ɔr/）", "our"),
    "oar": ("/ɔr/", "奥尔", "oar 组合发 /ɔr/", "board"),
    "oor": ("/ɔr/", "奥尔", "oor 组合发 /ɔr/", "door"),
    "oul": ("/ʊ/", "乌", "oul 在 could / would 中发 /ʊ/", "could"),
}

G2 = {
    # 二合辅音
    "sh": ("/ʃ/", "什", "sh 是一个音，不要拆成 s + h", "ship"),
    "ch": ("/tʃ/", "赤", "ch 常发 /tʃ/（少数读 /k/，如 school）", "chair"),
    "th": ("/θ/", "思", "th 清辅音，舌尖轻触齿间送气", "think"),
    "ph": ("/f/", "夫", "ph 组合发 /f/，多见于希腊词源", "photo"),
    "wh": ("/w/", "乌", "wh 常发 /w/（who 中读 /h/）", "what"),
    "ck": ("/k/", "克", "短元音后用 ck 表示 /k/", "duck"),
    "ng": ("/ŋ/", "嗯", "ng 是后鼻音 /ŋ/，舌根抵软腭", "sing"),
    "qu": ("/kw/", "克乌", "qu 永远读作 /kw/，q 不单独出现", "queen"),
    "wr": ("/r/", "若", "wr 中 w 不发音", "write"),
    "kn": ("/n/", "呢", "kn 中 k 不发音", "knee"),
    "gn": ("/n/", "呢", "gn 中 g 不发音", "sign"),
    "mb": ("/m/", "姆", "词尾 mb 中 b 不发音", "comb"),
    "gh": ("/f/", "夫", "gh 有时发 /f/，更多时候不发音", "laugh"),
    # 元音组合
    "ee": ("/iː/", "衣", "元音组合 ee 发长音 /iː/", "see"),
    "ea": ("/iː/", "衣", "ea 常发 /iː/（bread 中发 /ɛ/）", "sea"),
    "ai": ("/eɪ/", "诶", "ai 常发字母 A 的本音 /eɪ/", "rain"),
    "ay": ("/eɪ/", "诶", "词尾常用 ay 表示 /eɪ/", "play"),
    "oa": ("/oʊ/", "欧", "oa 发字母 O 的本音 /oʊ/", "boat"),
    "oo": ("/uː/", "乌", "oo 常发 /uː/（book 中发短音 /ʊ/）", "moon"),
    "ou": ("/aʊ/", "奥", "ou 常发 /aʊ/", "house"),
    "ow": ("/aʊ/", "奥", "ow 可发 /aʊ/（snow 中发 /oʊ/）", "cow"),
    "oi": ("/ɔɪ/", "奥伊", "oi 发 /ɔɪ/，用于词中", "coin"),
    "oy": ("/ɔɪ/", "奥伊", "oy 发 /ɔɪ/，常用于词尾", "boy"),
    "au": ("/ɔ/", "奥", "au 发 /ɔ/", "autumn"),
    "aw": ("/ɔ/", "奥", "aw 常用于词尾，发 /ɔ/", "saw"),
    "ie": ("/aɪ/", "艾", "ie 可发 /aɪ/（field 中发 /iː/）", "pie"),
    "ue": ("/uː/", "乌", "ue 常发 /uː/", "blue"),
    "ei": ("/eɪ/", "诶", "ei 有时发 /eɪ/", "eight"),
    "ey": ("/eɪ/", "诶", "词尾 ey 常发 /eɪ/", "they"),
    "ew": ("/uː/", "乌", "ew 常发 /uː/", "new"),
    # r 控元音
    "ar": ("/ɑr/", "阿尔", "r 控元音：ar 中的 a 被 r 改变", "car"),
    "er": ("/ər/", "厄", "r 控元音：er 发轻读 /ər/", "her"),
    "ir": ("/ər/", "厄", "r 控元音：ir 发 /ər/", "bird"),
    "or": ("/ɔr/", "奥尔", "r 控元音：or 发 /ɔr/", "for"),
    "ur": ("/ər/", "厄", "r 控元音：ur 发 /ər/", "nurse"),
}

# 辅音连缀：两个音依次读出，中间不停顿
BLENDS = {
    "bl": "black", "cl": "clock", "fl": "flag", "gl": "glass", "pl": "play",
    "sl": "sleep", "br": "brown", "cr": "cry", "dr": "dream", "fr": "friend",
    "gr": "green", "pr": "price", "tr": "tree", "st": "star", "sp": "speak",
    "sm": "smile", "sn": "snow", "sw": "swim", "tw": "twice", "sk": "skirt",
    "sc": "school", "str": "street", "spr": "spring", "scr": "screen",
}

DOUBLES = set("b d f g l m n p r s t z c".split())

G1 = {
    "a": ("/æ/", "艾", "闭音节中 a 发短音 /æ/", "cat"),
    "e": ("/ɛ/", "诶", "闭音节中 e 发短音 /ɛ/", "bed"),
    "i": ("/ɪ/", "伊", "闭音节中 i 发短音 /ɪ/", "sit"),
    "o": ("/ɑ/", "阿", "闭音节中 o 发短音 /ɑ/", "hot"),
    "u": ("/ʌ/", "阿", "闭音节中 u 发短音 /ʌ/", "cup"),
    "b": ("/b/", "波", "辅音 b", "book"),
    "c": ("/k/", "克", "c 在 a/o/u 前发 /k/（在 e/i/y 前发 /s/）", "cat"),
    "d": ("/d/", "得", "辅音 d", "dog"),
    "f": ("/f/", "夫", "辅音 f", "fish"),
    "g": ("/g/", "哥", "g 在 a/o/u 前发 /g/（在 e/i/y 前常发 /dʒ/）", "go"),
    "h": ("/h/", "喝", "辅音 h，轻送气", "hat"),
    "j": ("/dʒ/", "吉", "辅音 j", "jump"),
    "k": ("/k/", "克", "辅音 k", "key"),
    "l": ("/l/", "勒", "辅音 l", "leg"),
    "m": ("/m/", "姆", "辅音 m", "map"),
    "n": ("/n/", "呢", "辅音 n", "net"),
    "p": ("/p/", "普", "辅音 p", "pen"),
    "q": ("/k/", "克", "q 通常与 u 组成 qu", "queen"),
    "r": ("/r/", "若", "辅音 r，舌尖卷起不触上颚", "red"),
    "s": ("/s/", "斯", "辅音 s（在两元音间常读 /z/）", "sun"),
    "t": ("/t/", "特", "辅音 t", "top"),
    "v": ("/v/", "夫", "辅音 v，上齿轻咬下唇振动", "van"),
    "w": ("/w/", "乌", "辅音 w", "water"),
    "x": ("/ks/", "克斯", "x 通常发 /ks/", "box"),
    "y": ("/j/", "耶", "词首 y 作辅音 /j/；词中词尾作元音", "yes"),
    "z": ("/z/", "兹", "辅音 z", "zoo"),
}

LONG_VOWEL = {"a": "/eɪ/", "e": "/iː/", "i": "/aɪ/", "o": "/oʊ/", "u": "/juː/"}
VOWELS = "aeiouy"


def split_syllables(word):
    """启发式音节划分：元音组之间按 VC/CV 规则切分。"""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return []
    groups = []
    i = 0
    while i < len(w):
        if w[i] in VOWELS:
            j = i
            while j < len(w) and w[j] in VOWELS:
                j += 1
            groups.append((i, j))
            i = j
        else:
            i += 1
    if len(groups) <= 1:
        return [w]
    # 词尾不发音的 e 不构成独立音节
    if w.endswith("e") and len(w) > 2 and groups[-1][0] == len(w) - 1:
        groups = groups[:-1]
    if len(groups) <= 1:
        return [w]
    bounds = []
    for k in range(len(groups) - 1):
        a_end, b_start = groups[k][1], groups[k + 1][0]
        cons = w[a_end:b_start]
        if len(cons) <= 1:
            cut = a_end          # 单个辅音归后一音节：pho-to-graph
        elif cons in BLENDS or len(cons) >= 3 and cons[-2:] in BLENDS:
            cut = a_end          # 辅音连缀整体归后一音节
        elif len(cons) == 2:
            cut = a_end + 1      # 两个辅音平分：hel-lo
        else:
            cut = a_end + len(cons) - 1
        bounds.append(cut)
    parts, prev = [], 0
    for cut in bounds:
        if cut > prev:
            parts.append(w[prev:cut])
            prev = cut
    parts.append(w[prev:])
    return [p for p in parts if p]


def _chunk(letters, ipa, hint, rule, example):
    return {"letters": letters, "ipa": ipa, "hint": hint, "rule": rule, "example": example}


def analyze(word, ipa=""):
    """返回拼读拆解结果。word 可含空格，仅取第一个英文单词。"""
    raw = (word or "").strip()
    m = re.search(r"[A-Za-z][A-Za-z'-]*", raw)
    if not m:
        return {"ok": False, "reason": "当前选中内容没有英文单词"}
    w = m.group(0).lower()
    if len(w) > 24:
        return {"ok": False, "reason": "单词过长，拼读解析仅支持 24 个字母以内"}

    silent_e = w.endswith("e") and len(w) > 3 and w[-2] not in VOWELS and not w.endswith("ee") and not w.endswith("oe")
    body = w[:-1] if silent_e else w
    chunks, rules, seen = [], [], set()

    def add_rule(r):
        if r and r not in seen:
            seen.add(r)
            rules.append(r)

    i = 0
    while i < len(body):
        hit = None
        for size in (3, 2):
            seg = body[i:i + size]
            table = G3 if size == 3 else G2
            if len(seg) == size and seg in table:
                hit = (seg, table[seg])
                break
        if hit:
            seg, (ipa_s, hint, rule, ex) = hit
            chunks.append(_chunk(seg, ipa_s, hint, rule, ex))
            add_rule(rule)
            i += len(seg)
            continue
        # 辅音连缀
        seg2 = body[i:i + 2]
        if seg2 in BLENDS:
            chunks.append(_chunk(seg2, "/" + seg2[0] + seg2[1] + "/", "连读",
                                 "辅音连缀 " + seg2 + "：两个辅音快速连读，中间不插入元音", BLENDS[seg2]))
            add_rule("含辅音连缀 " + seg2 + "，两个音要连起来读，不要断开")
            i += 2
            continue
        if len(seg2) == 2 and seg2[0] == seg2[1] and seg2[0] in DOUBLES:
            one = seg2[0]
            ipa_s, hint, _, ex = G1.get(one, ("/" + one + "/", "", "", one))
            chunks.append(_chunk(seg2, ipa_s, hint, "双写辅音只读一次，前面元音通常读短音", ex))
            add_rule("双写辅音 " + seg2 + " 只读一个音，提示前面的元音是短音")
            i += 2
            continue
        ch = body[i]
        ipa_s, hint, rule, ex = G1.get(ch, ("/" + ch + "/", "", "", ch))
        # 软 c / 软 g
        nxt = body[i + 1] if i + 1 < len(body) else ""
        if ch == "c" and nxt in "eiy":
            ipa_s, hint, rule, ex = "/s/", "斯", "软 c：c 在 e / i / y 前发 /s/", "city"
            add_rule(rule)
        elif ch == "g" and nxt in "eiy":
            ipa_s, hint, rule, ex = "/dʒ/", "吉", "软 g：g 在 e / i / y 前常发 /dʒ/", "gem"
            add_rule(rule)
        elif ch == "y" and i > 0:
            ipa_s, hint, rule, ex = "/ɪ/", "伊", "词中/词尾 y 作元音，常发 /ɪ/ 或 /aɪ/", "happy"
        # 开音节：单个元音字母结尾也常读长音
        if ch in LONG_VOWEL and i == len(body) - 1 and len(body) > 1 and not silent_e:
            ipa_s = LONG_VOWEL[ch]
            hint = "字母本音"
            rule = "开音节：元音字母位于音节末尾时读字母本音 " + ipa_s
            add_rule(rule)
        chunks.append(_chunk(ch, ipa_s, hint, rule, ex))
        i += 1

    if silent_e:
        # 主体最后一个单字母元音改为长音
        for idx in range(len(chunks) - 1, -1, -1):
            c = chunks[idx]
            if c["letters"] in LONG_VOWEL and len(c["letters"]) == 1:
                c["ipa"] = LONG_VOWEL[c["letters"]]
                c["hint"] = "字母本音"
                c["rule"] = "Magic E：词尾 e 不发音，让前面的 " + c["letters"] + " 读字母本音 " + c["ipa"]
                add_rule(c["rule"])
                break
        chunks.append(_chunk("e", "不发音", "静音", "Magic E：词尾 e 本身不发音，只改变前面元音的读法", "cake"))
        add_rule("Magic E（神奇 e）：词尾 e 不发音，前面的元音读字母本音")

    syllables = split_syllables(w)
    note = "共 %d 个音节：%s。" % (len(syllables), " · ".join(syllables))
    if silent_e:
        note += " 含 Magic E 结构，先找词尾不发音的 e，再倒推前一个元音读长音。"
    elif any(c["letters"] in ("ar", "er", "ir", "or", "ur") for c in chunks):
        note += " 含 r 控元音，元音被后面的 r 改变，不要按普通短音读。"
    else:
        note += " 从左到右按字母组合逐块拼读，再把各块连起来。"

    return {
        "ok": True,
        "word": w,
        "ipa": ipa,
        "syllables": syllables,
        "chunks": chunks,
        "rules": rules[:8],
        "note": note,
    }
