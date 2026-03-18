(function () {
  const transcriptEl = document.getElementById("transcript");
  const transcriptScrollEl = document.getElementById("transcript-scroll");
  let mathTimer = null;
  let liveAssistant = null;
  let qtClipboardBridge = null;

  function bindQtClipboard() {
    if (!window.qt || !window.QWebChannel || qtClipboardBridge) return;
    try {
      new QWebChannel(window.qt.webChannelTransport, function (channel) {
        qtClipboardBridge = channel.objects ? channel.objects.clipboardBridge || null : null;
      });
    } catch (_err) {
      qtClipboardBridge = null;
    }
  }

  bindQtClipboard();

  function scheduleMathTypeset(target) {
    if (mathTimer) {
      clearTimeout(mathTimer);
      mathTimer = null;
    }
    mathTimer = setTimeout(function () {
      if (window.MathJax && window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise([target || transcriptEl]).catch(function () {
          return;
        });
      }
    }, 60);
  }

  function decodeRawB64(value) {
    try {
      const bin = atob(String(value || ""));
      const bytes = Uint8Array.from(bin, function (c) {
        return c.charCodeAt(0);
      });
      return new TextDecoder("utf-8").decode(bytes);
    } catch (_err) {
      return "";
    }
  }

  function copyFallback(text) {
    const ta = document.createElement("textarea");
    ta.value = String(text || "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (_err) {
      ok = false;
    }
    document.body.removeChild(ta);
    return ok;
  }

  async function copyText(text) {
    const payload = String(text || "");
    if (!payload) return false;
    if (qtClipboardBridge && typeof qtClipboardBridge.copyText === "function") {
      try {
        const ok = await new Promise(function (resolve) {
          qtClipboardBridge.copyText(payload, function (result) {
            resolve(Boolean(result));
          });
        });
        if (ok) return true;
      } catch (_err) {
      }
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(payload);
        return true;
      }
    } catch (_err) {
    }
    return copyFallback(payload);
  }

  function flashCopyState(button, ok) {
    if (!button) return;
    const original = button.dataset.copyLabel || button.textContent || "Copy";
    button.dataset.copyLabel = original;
    button.textContent = ok ? "Copied" : "Failed";
    button.disabled = true;
    window.setTimeout(function () {
      button.textContent = original;
      button.disabled = false;
    }, ok ? 900 : 1200);
  }

  function decorateCodeBlocks(scopeNode) {
    const root = scopeNode || transcriptEl;
    if (!root) return;
    root.querySelectorAll("pre").forEach(function (pre) {
      if (pre.querySelector(".copy-code-btn")) return;
      const code = pre.querySelector("code");
      if (!code) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "copy-code-btn";
      btn.title = "Copy code";
      btn.setAttribute("aria-label", "Copy code");
      btn.textContent = "Copy";
      pre.insertBefore(btn, pre.firstChild);
    });
  }

  function scrollBottom() {
    transcriptScrollEl.scrollTop = transcriptScrollEl.scrollHeight;
  }

  function createStreamWriter(bodyNode) {
    const state = {
      active: true,
      queue: "",
      rafId: 0,
    };

    function charsPerFrame() {
      const queued = state.queue.length;
      if (queued > 1200) return 72;
      if (queued > 640) return 44;
      if (queued > 260) return 24;
      if (queued > 96) return 12;
      if (queued > 24) return 6;
      return 2;
    }

    function flushFrame() {
      state.rafId = 0;
      if (!state.active || !state.queue) {
        return;
      }
      const take = Math.min(charsPerFrame(), state.queue.length);
      const slice = state.queue.slice(0, take);
      state.queue = state.queue.slice(take);
      bodyNode.textContent += slice;
      bodyNode.dataset.rawText = (bodyNode.dataset.rawText || "") + slice;
      scrollBottom();
      if (state.queue) {
        state.rafId = window.requestAnimationFrame(flushFrame);
      }
    }

    function ensureRunning() {
      if (!state.active || state.rafId) return;
      state.rafId = window.requestAnimationFrame(flushFrame);
    }

    return {
      push: function (text) {
        if (!state.active) return;
        const chunk = String(text || "");
        if (!chunk) return;
        state.queue += chunk;
        ensureRunning();
      },
      flushAll: function () {
        if (!state.active) return;
        if (state.rafId) {
          window.cancelAnimationFrame(state.rafId);
          state.rafId = 0;
        }
        if (!state.queue) return;
        bodyNode.textContent += state.queue;
        bodyNode.dataset.rawText = (bodyNode.dataset.rawText || "") + state.queue;
        state.queue = "";
        scrollBottom();
        return;
      },
      stop: function () {
        state.active = false;
        if (state.rafId) {
          window.cancelAnimationFrame(state.rafId);
          state.rafId = 0;
        }
        state.queue = "";
      },
    };
  }

  function roleLabel(role) {
    if (role === "assistant") return "Athena";
    if (role === "system") return "System";
    return "You";
  }

  function roleIcon(role) {
    if (role === "assistant") return "\u{1F9E0}";
    if (role === "system") return "\u2699\uFE0F";
    return "\u{1F9D1}";
  }

  function appendLiveMessage(role, text, imageUrls) {
    const article = document.createElement("article");
    article.className = "msg " + role;

    const avatar = document.createElement("aside");
    avatar.className = "avatar";
    avatar.textContent = roleIcon(role);

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const head = document.createElement("div");
    head.className = "bubble-head";
    const pill = document.createElement("span");
    pill.className = "role-pill";
    const icon = document.createElement("span");
    icon.className = "role-icon";
    icon.textContent = roleIcon(role);
    pill.appendChild(icon);
    pill.appendChild(document.createTextNode(roleLabel(role)));
    head.appendChild(pill);

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "copy-msg-btn";
    copyBtn.textContent = "Copy";
    head.appendChild(copyBtn);

    const body = document.createElement("section");
    body.className = "msg-body";
    body.style.whiteSpace = "pre-wrap";
    body.textContent = String(text || "");
    body.dataset.rawText = String(text || "");

    (imageUrls || []).forEach(function (url, idx) {
      if (!url) return;
      const img = document.createElement("img");
      img.loading = "lazy";
      img.decoding = "async";
      img.alt = "attached image " + String(idx + 1);
      img.src = url;
      body.appendChild(document.createElement("br"));
      body.appendChild(img);
    });

    bubble.appendChild(head);
    bubble.appendChild(body);
    article.appendChild(avatar);
    article.appendChild(bubble);
    transcriptEl.appendChild(article);
    scrollBottom();
    return { article, body };
  }

  window.AthenaDesktopTranscript = {
    setTranscriptHtml: function (html) {
      if (liveAssistant && liveAssistant.typer) {
        liveAssistant.typer.stop();
      }
      liveAssistant = null;
      transcriptEl.innerHTML = html || "";
      decorateCodeBlocks(transcriptEl);
      scheduleMathTypeset(transcriptEl);
      scrollBottom();
    },
    appendLiveMessage: function (role, text, imageUrls) {
      appendLiveMessage(String(role || "system"), String(text || ""), Array.isArray(imageUrls) ? imageUrls : []);
    },
    beginAssistantMessage: function () {
      if (liveAssistant && liveAssistant.typer) {
        liveAssistant.typer.flushAll();
      }
      const live = appendLiveMessage("assistant", "", []);
      live.article.classList.add("streaming");
      live.typer = createStreamWriter(live.body);
      liveAssistant = live;
    },
    appendAssistantDelta: function (text) {
      if (!liveAssistant) {
        this.beginAssistantMessage();
      }
      liveAssistant.typer.push(String(text || ""));
    },
  };

  transcriptEl.addEventListener("click", async function (event) {
    const target = event.target;
    if (!target || !target.classList) return;
    if (target.classList.contains("copy-msg-btn")) {
      const msg = target.closest(".msg");
      const body = msg ? msg.querySelector(".msg-body") : null;
      const raw = body ? body.dataset.rawText || decodeRawB64(body.getAttribute("data-raw-b64")) || body.textContent || "" : "";
      flashCopyState(target, await copyText(raw));
      return;
    }
    if (target.classList.contains("copy-code-btn")) {
      const pre = target.closest("pre");
      const code = pre ? pre.querySelector("code") : null;
      flashCopyState(target, await copyText(code ? code.textContent || "" : ""));
    }
  });
})();
