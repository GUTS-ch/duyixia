/* LingoRead 前端：欧路词典式界面逻辑 */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var cfg = {}, voices = [], current = "", currentItem = null, playSeq = 0, audioUrl = "", lastCost = "";
  var audio = $("player");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function status(msg, busy) {
    $("status").textContent = msg;
    $("statusDot").className = "dot" + (busy ? " busy" : "");
  }
  function api(path, body) {
    return fetch(path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    });
  }
  function isWord(t) { return /^[A-Za-z][A-Za-z'-]{0,23}$/.test((t || "").trim()); }
  function shortTitle(t) {
    t = (t || "").trim();
    if (isWord(t)) return t;
    var parts = t.split(/\s+/).slice(0, 6).join(" ");
    return parts + (t.split(/\s+/).length > 6 ? " …" : "");
  }

  /* ------------------------------------------------ 朗读 */
  function speak(text, voice) {
    text = (text || "").trim();
    if (!text) return;
    var seq = ++playSeq, t0 = Date.now();
    status("正在合成发音…", true);
    api("/api/tts", { text: text, voice: voice || cfg.voice }).then(function (r) {
      return r.blob().then(function (b) { return { blob: b, engine: r.headers.get("X-TTS-Engine") }; });
    }).then(function (o) {
      if (seq !== playSeq || !o.blob.size) return;
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audioUrl = URL.createObjectURL(o.blob);
      audio.src = audioUrl;
      audio.play().catch(function () { status("播放被阻止，请点击朗读按钮"); });
      var names = { edge: "美式神经音", fast: "快速发音", sapi: "系统语音（离线）", fail: "发音失败" };
      lastCost = ((Date.now() - t0) / 1000).toFixed(2);
      $("engineTag").textContent = names[o.engine] || "已朗读";
      status(o.engine === "fail" ? "发音失败，请检查网络"
        : "发音 " + lastCost + "s · " + (names[o.engine] || "已朗读"), false);
    }).catch(function () { status("发音请求失败", false); });
  }
  audio.onended = function () { status(lastCost ? "发音 " + lastCost + "s · 播放完成" : "播放完成", false); };

  /* ------------------------------------------------ 翻译 */
  function translate(text) {
    if (!text) return;
    $("trEngine").textContent = "翻译中…";
    $("translation").className = "translation";
    $("translation").textContent = "正在请求翻译服务…";
    $("trNotice").className = "tr-notice";
    $("trNotice").textContent = "";
    api("/api/translate", { text: text }).then(function (r) { return r.json(); }).then(function (d) {
      $("trNotice").className = "tr-notice" + (d.notice ? " show" : "");
      $("trNotice").textContent = d.notice || "";
      if (d.ok) {
        $("translation").textContent = d.text;
        $("trEngine").textContent = d.engine;
        if (currentItem) currentItem.translation = d.text;
        status("翻译完成 · " + d.engine, false);
      } else {
        $("translation").className = "translation error";
        $("translation").textContent = "翻译失败：" + (d.error || "网络不可用");
        $("trEngine").textContent = "失败";
        status("翻译失败", false);
      }
    }).catch(function () {
      $("translation").className = "translation error";
      $("translation").textContent = "无法连接本地服务";
    });
  }

  /* ------------------------------------------------ 拼读 */
  function renderPhonics(d) {
    var chunksHtml = "", rulesHtml = "", sylHtml = "";
    if (!d.ok) {
      $("phIpa").textContent = "";
      $("syllables").innerHTML = "";
      $("chunks").innerHTML = '<div class="empty">' + esc(d.reason) + "</div>";
      $("chunksBig").innerHTML = '<div class="empty">' + esc(d.reason) + "</div>";
      $("phNote").textContent = "选中一个英文单词即可查看自然拼读拆解。";
      $("phRules").innerHTML = "";
      $("phRulesBig").innerHTML = "";
      $("phHero").textContent = "等待单词";
      $("phWordBig").textContent = "";
      return;
    }
    $("phIpa").textContent = d.ipa ? "/ " + d.ipa + " /" : "美式音标";
    $("usphone").textContent = d.ipa ? "美 /" + d.ipa + "/" : "";
    $("ukphone").textContent = d.ukphone ? "英 /" + d.ukphone + "/" : "";
    (d.senses || []).forEach(function (s) {
      $("senses").innerHTML += '<span class="sense">' + esc(s) + "</span>";
    });
    (d.syllables || []).forEach(function (s) { sylHtml += '<span class="syl">' + esc(s) + "</span>"; });
    (d.chunks || []).forEach(function (c) {
      chunksHtml += '<div class="chunk" data-ex="' + esc(c.example) + '" title="' + esc(c.rule) + '">' +
        '<span class="letters">' + esc(c.letters) + "</span>" +
        '<span class="ipa">' + esc(c.ipa) + "</span>" +
        '<span class="hint">' + esc(c.hint) + "</span></div>";
    });
    (d.rules || []).forEach(function (r) { rulesHtml += '<div class="rule">' + esc(r) + "</div>"; });
    $("syllables").innerHTML = sylHtml;
    $("chunks").innerHTML = chunksHtml;
    $("chunksBig").innerHTML = chunksHtml;
    $("phNote").textContent = d.note || "";
    $("phRules").innerHTML = rulesHtml;
    $("phRulesBig").innerHTML = rulesHtml;
    $("phHero").textContent = d.word;
    $("phWordBig").textContent = (d.syllables || []).length + " 个音节";
    document.querySelectorAll(".chunk").forEach(function (el) {
      el.addEventListener("click", function () { speak(el.getAttribute("data-ex")); });
    });
  }

  function phonics(text) {
    if (!isWord(text)) {
      renderPhonics({ ok: false, reason: "句子不做拼读拆解，请选中单个英文单词" });
      return;
    }
    $("phIpa").textContent = "解析中…";
    api("/api/phonics", { word: text }).then(function (r) { return r.json(); })
      .then(renderPhonics).catch(function () { $("phIpa").textContent = "解析失败"; });
  }

  /* ------------------------------------------------ 主流程 */
  function handleSelection(text, opts) {
    opts = opts || {};
    text = (text || "").trim();
    if (!text) return;
    current = text;
    currentItem = { text: text, ts: Date.now(), translation: "" };
    $("q").value = text;
    $("wordTitle").textContent = shortTitle(text);
    $("entryType").textContent = isWord(text) ? "单词 / WORD" : "选中文本 / SELECTION";
    $("origin").textContent = text;
    $("lenTag").textContent = text.length + " 字符";
    $("senses").innerHTML = "";
    $("usphone").textContent = "";
    $("ukphone").textContent = "";
    $("favBtn").className = "icon-btn big";
    if (!opts.silent && cfg.auto_speak !== false) speak(text);
    if (cfg.auto_translate !== false) translate(text); else { $("translation").textContent = "自动翻译已关闭"; $("trEngine").textContent = "未翻译"; }
    if (cfg.auto_phonics !== false && isWord(text)) phonics(text);
    else if (!isWord(text)) renderPhonics({ ok: false, reason: "句子不做拼读拆解，请选中单个英文单词" });
    api("/api/history", { action: "add", item: currentItem });
    loadLists();
  }

  /* ------------------------------------------------ 历史 / 生词本 */
  function loadLists() {
    fetch("/api/history").then(function (r) { return r.json(); }).then(function (d) {
      var h = d.history || [], f = d.favorites || [];
      $("favCount").textContent = f.length + " 条";
      $("historyList").innerHTML = h.length ? h.map(function (x) {
        return '<div class="list-item" data-t="' + esc(x.text) + '"><span class="txt">' + esc(x.text) +
          '</span><span class="sub">' + esc((x.translation || "").slice(0, 22)) +
          '</span><button data-clear="1">隐藏</button></div>';
      }).join("") : '<div class="empty">还没有查询记录</div>';
      $("favList").innerHTML = f.length ? f.map(function (x) {
        return '<div class="list-item" data-t="' + esc(x.text) + '"><span class="txt">' + esc(x.text) +
          '</span><button data-unfav="' + esc(x.text) + '">移除</button></div>';
      }).join("") : '<div class="empty">点击词条右上角的星标加入生词本</div>';
      var favTexts = f.map(function (x) { return x.text; });
      if (current && favTexts.indexOf(current) >= 0) $("favBtn").className = "icon-btn big on";
      document.querySelectorAll(".list-item").forEach(function (el) {
        el.addEventListener("click", function (e) {
          var t = el.getAttribute("data-t");
          if (e.target.getAttribute("data-unfav")) {
            api("/api/history", { action: "unfavorite", item: { text: t } }).then(loadLists);
            return;
          }
          if (e.target.getAttribute("data-clear")) return;
          showView("query");
          handleSelection(t);
        });
      });
      $("clearHistory").onclick = function () { api("/api/history", { action: "clear" }).then(loadLists); };
    });
  }

  /* ------------------------------------------------ 自定义快捷键 */
  var hk = { mods: 6, vk: 83, label: "Ctrl + Shift + S" }, capturing = false;
  var MOD_NAMES = [[2, "Ctrl"], [1, "Alt"], [4, "Shift"], [8, "Win"]];
  var SPECIAL_VK = {
    Space: 0x20, Enter: 0x0D, NumpadEnter: 0x0D, Tab: 0x09,
    Backquote: 0xC0, Minus: 0xBD, Equal: 0xBB, BracketLeft: 0xDB,
    BracketRight: 0xDD, Backslash: 0xDC, Semicolon: 0xBA, Quote: 0xDE,
    Comma: 0xBC, Period: 0xBE, Slash: 0xBF,
    Insert: 0x2D, Delete: 0x2E, Home: 0x24, End: 0x23,
    PageUp: 0x21, PageDown: 0x22,
    ArrowUp: 0x26, ArrowDown: 0x28, ArrowLeft: 0x25, ArrowRight: 0x27,
    NumpadMultiply: 0x6A, NumpadAdd: 0x6B, NumpadSubtract: 0x6D,
    NumpadDecimal: 0x6E, NumpadDivide: 0x6F
  };
  var KEY_NAMES = {
    Space: "空格", Enter: "回车", NumpadEnter: "小键盘回车", Tab: "Tab",
    Backquote: "`", Minus: "-", Equal: "=", BracketLeft: "[", BracketRight: "]",
    Backslash: "\\", Semicolon: ";", Quote: "'", Comma: ",", Period: ".", Slash: "/",
    Insert: "Insert", Delete: "Delete", Home: "Home", End: "End",
    PageUp: "PageUp", PageDown: "PageDown",
    ArrowUp: "↑", ArrowDown: "↓", ArrowLeft: "←", ArrowRight: "→"
  };
  function vkFromCode(code) {
    if (/^Key[A-Z]$/.test(code)) return code.charCodeAt(3);
    if (/^Digit\d$/.test(code)) return 0x30 + parseInt(code.slice(5), 10);
    if (/^Numpad\d$/.test(code)) return 0x60 + parseInt(code.slice(6), 10);
    if (/^F([1-9]|1\d|2[0-4])$/.test(code)) return 0x70 + parseInt(code.slice(1), 10) - 1;
    return SPECIAL_VK[code] || 0;
  }
  function nameFromCode(code, key) {
    if (/^Key[A-Z]$/.test(code)) return code.slice(3);
    if (/^Digit\d$/.test(code)) return code.slice(5);
    if (/^Numpad\d$/.test(code)) return "小键盘" + code.slice(6);
    if (KEY_NAMES[code]) return KEY_NAMES[code];
    if (/^F\d+$/.test(code)) return code;
    return (key && key.length === 1) ? key.toUpperCase() : (key || "");
  }
  function singleKeyAllowed(vk) {
    return (vk >= 0x70 && vk <= 0x87) || [0x2D, 0x2E, 0x21, 0x22, 0x23, 0x24].indexOf(vk) >= 0;
  }
  function renderHotkey() {
    $("hkCapture").textContent = hk.label;
    $("hotkeyChip").textContent = hk.label;
    $("hotkeyInline").textContent = hk.label;
  }
  function hkMessage(text, ok) {
    $("hkMsg").textContent = text;
    $("hkMsg").className = "hk-msg show " + (ok ? "ok" : "err");
  }
  function setCapturing(on) {
    capturing = !!on;
    $("hkCapture").classList.toggle("capturing", capturing);
    $("hkCapture").textContent = capturing ? "请按下组合键…（Esc 取消）" : hk.label;
  }
  function applyHotkey() {
    api("/api/settings", { config: { hotkey_mods: hk.mods, hotkey_vk: hk.vk, hotkey: hk.label } })
      .then(function (r) { return r.json(); }).then(function (d) {
        if (d.hotkey_ok === false) {
          hk = { mods: d.config.hotkey_mods, vk: d.config.hotkey_vk,
                 label: d.config.hotkey || "Ctrl + Shift + S" };
          renderHotkey();
          hkMessage(d.hotkey_error || "快捷键设置失败，请换一组", false);
          return;
        }
        cfg = d.config;
        hkMessage("已生效：" + hk.label + "（选中英文后按此键即可朗读）", true);
      }).catch(function () { hkMessage("无法连接本地服务", false); });
  }
  function onCaptureKey(e) {
    if (!capturing) return;
    e.preventDefault();
    e.stopPropagation();
    if (e.key === "Escape" || e.code === "Escape") { setCapturing(false); return; }
    if (["Control", "Shift", "Alt", "Meta"].indexOf(e.key) >= 0) return;
    var mods = (e.ctrlKey ? 2 : 0) | (e.altKey ? 1 : 0) |
               (e.shiftKey ? 4 : 0) | (e.metaKey ? 8 : 0);
    var vk = vkFromCode(e.code || "");
    if (!vk) { hkMessage("不支持这个按键，请换一个", false); return; }
    if (!mods && !singleKeyAllowed(vk)) {
      hkMessage("请至少按住 Ctrl / Alt / Shift 中的一个，或改用 F1–F12 等功能键", false);
      return;
    }
    var parts = [];
    MOD_NAMES.forEach(function (m) { if (mods & m[0]) parts.push(m[1]); });
    parts.push(nameFromCode(e.code || "", e.key));
    hk = { mods: mods, vk: vk, label: parts.join(" + ") };
    setCapturing(false);
    renderHotkey();
    applyHotkey();
  }
  function focusHotkeyField() {
    showView("settings");
    var f = $("hotkeyField");
    try { f.scrollIntoView({ block: "center" }); } catch (err) { /* ignore */ }
    f.classList.add("focus");
    setTimeout(function () { f.classList.remove("focus"); }, 2600);
    $("hkCapture").focus();
  }

  /* ------------------------------------------------ 视图 / 设置 */
  function showView(name) {
    document.querySelectorAll(".view").forEach(function (v) {
      v.classList.toggle("hidden", v.id !== "view-" + name);
    });
    document.querySelectorAll(".rail-btn").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-view") === name);
    });
    if (name === "history" || name === "favorites") loadLists();
  }

  function applyTheme() {
    document.body.classList.toggle("dark", cfg.theme === "dark");
    $("setTheme").checked = cfg.theme === "dark";
  }
  function fillSettings() {
    $("setVoice").innerHTML = voices.map(function (v) {
      return '<option value="' + v.id + '">' + esc(v.name) + " — " + esc(v.desc) + "</option>";
    }).join("");
    $("setVoice").value = cfg.voice || voices[0].id;
    $("voiceDesc").textContent = (voices.filter(function (v) { return v.id === cfg.voice; })[0] || voices[0]).desc;
    $("setWordVoice").value = cfg.word_voice || "dict";
    $("setStartMin").checked = !!cfg.start_minimized;
    $("setTrayOpen").checked = !!cfg.tray_auto_open;
    $("setBalloon").checked = cfg.show_balloon !== false;
    hk = {
      mods: (typeof cfg.hotkey_mods === "number") ? cfg.hotkey_mods : 6,
      vk: (typeof cfg.hotkey_vk === "number") ? cfg.hotkey_vk : 0x53,
      label: cfg.hotkey || "Ctrl + Shift + S"
    };
    setCapturing(false);
    renderHotkey();
    $("hkMsg").className = "hk-msg";
    $("setEngine").value = cfg.translate_engine || "baidu";
    $("setBaiduAppid").value = cfg.baidu_appid || "";
    $("setBaiduSecret").value = cfg.baidu_secret || "";
    $("setApiUrl").value = cfg.custom_api_url || "";
    $("setApiKey").value = cfg.custom_api_key || "";
    $("setLang").value = cfg.target_lang || "zh-CN";
    $("setAutoSpeak").checked = cfg.auto_speak !== false;
    $("setAutoTranslate").checked = cfg.auto_translate !== false;
    $("setAutoPhonics").checked = cfg.auto_phonics !== false;
    $("setAutostart").checked = !!cfg.autostart;
    $("voiceTag").textContent = (voices.filter(function (v) { return v.id === cfg.voice; })[0] || {}).name || "美式神经音";
    applyTheme();
  }

  function saveSettings() {
    var patch = {
      voice: $("setVoice").value,
      word_voice: $("setWordVoice").value,
      hotkey_mods: hk.mods, hotkey_vk: hk.vk, hotkey: hk.label,
      start_minimized: $("setStartMin").checked,
      tray_auto_open: $("setTrayOpen").checked,
      show_balloon: $("setBalloon").checked,
      translate_engine: $("setEngine").value,
      baidu_appid: $("setBaiduAppid").value.trim(),
      baidu_secret: $("setBaiduSecret").value.trim(),
      custom_api_url: $("setApiUrl").value.trim(),
      custom_api_key: $("setApiKey").value.trim(),
      target_lang: $("setLang").value,
      auto_speak: $("setAutoSpeak").checked,
      auto_translate: $("setAutoTranslate").checked,
      auto_phonics: $("setAutoPhonics").checked,
      autostart: $("setAutostart").checked,
      theme: $("setTheme").checked ? "dark" : "light"
    };
    api("/api/settings", { config: patch }).then(function (r) { return r.json(); }).then(function (d) {
      cfg = d.config;
      fillSettings();
      if (d.hotkey_ok === false) {
        hkMessage(d.hotkey_error || "快捷键未生效，已保留原来的组合", false);
        status("快捷键未生效", false);
      } else {
        hkMessage("已生效：" + hk.label, true);
        status("设置已保存", false);
      }
    });
  }

  /* ------------------------------------------------ 事件绑定 */
  document.querySelectorAll(".rail-btn").forEach(function (b) {
    b.addEventListener("click", function () { showView(b.getAttribute("data-view")); });
  });
  $("btnQuery").onclick = function () { handleSelection($("q").value); };
  $("btnSpeak").onclick = function () { speak($("q").value || current); };
  $("btnReplay").onclick = function () { speak(current || $("q").value); };
  $("q").addEventListener("keydown", function (e) { if (e.key === "Enter") handleSelection($("q").value); });
  $("trRetry").onclick = function () { translate(current || $("q").value); };
  $("btnSave").onclick = saveSettings;
  $("hkCapture").onclick = function () {
    $("hkMsg").className = "hk-msg";
    setCapturing(true);
  };
  $("hkReset").onclick = function () {
    setCapturing(false);
    hk = { mods: 6, vk: 0x53, label: "Ctrl + Shift + S" };
    renderHotkey();
    applyHotkey();
  };
  document.querySelectorAll("#hkPresets button").forEach(function (b) {
    b.addEventListener("click", function () {
      setCapturing(false);
      hk = { mods: parseInt(b.getAttribute("data-mods"), 10),
             vk: parseInt(b.getAttribute("data-vk"), 10),
             label: b.getAttribute("data-label") };
      renderHotkey();
      applyHotkey();
    });
  });
  document.addEventListener("keydown", onCaptureKey, true);
  $("themeBtn").onclick = function () {
    cfg.theme = cfg.theme === "dark" ? "light" : "dark";
    applyTheme();
    api("/api/settings", { config: { theme: cfg.theme } });
  };
  $("setTheme").onchange = applyTheme;
  $("setVoice").onchange = function () {
    $("voiceDesc").textContent = (voices.filter(function (v) { return v.id === this.value; }.bind(this))[0] || {}).desc || "";
  };
  $("favBtn").onclick = function () {
    if (!current) return;
    api("/api/history", { action: "favorite", item: currentItem || { text: current, ts: Date.now() } })
      .then(loadLists);
  };
  $("btnQuit").onclick = function () {
    if (confirm("退出读一下？重新双击 读一下.exe 即可打开。")) api("/api/quit", {});
  };

  /* ------------------------------------------------ SSE */
  function connect() {
    var es = new EventSource("/api/events");
    es.addEventListener("selection", function (e) {
      var d = JSON.parse(e.data);
      handleSelection(d.text);
      status("已抓取选中文字", false);
    });
    es.addEventListener("status", function (e) { status(JSON.parse(e.data).text, false); });
    es.addEventListener("navigate", function (e) {
      var d = JSON.parse(e.data);
      if (d.focus === "hotkey") focusHotkeyField(); else showView(d.view);
    });
    es.addEventListener("quit", function () {
      status("程序已退出", false);
      try { window.close(); } catch (err) { /* ignore */ }
    });
    es.onerror = function () { status("本地连接断开，正在重连…", true); };
    es.onopen = function () { status("就绪 · 等待抓取", false); };
  }

  /* ------------------------------------------------ 初始化 */
  fetch("/api/state").then(function (r) { return r.json(); }).then(function (d) {
    cfg = d.config; voices = d.voices;
    $("installPath").textContent = d.install_dir || "";
    fillSettings();
    loadLists();
    connect();
    // 托盘菜单「设置 / 设置快捷键」打开窗口时带参数，保证新窗口也能直达
    var params = new URLSearchParams(location.search);
    if (params.get("view")) showView(params.get("view"));
    if (params.get("focus") === "hotkey") setTimeout(focusHotkeyField, 150);
    // 托盘模式下自动打开窗口时，后端已朗读过，这里只补显示翻译与拼读
    if (params.get("auto") === "1" && d.last_result && d.last_result.text) {
      showView("query");
      handleSelection(d.last_result.text, { silent: true });
    }
  });
})();
