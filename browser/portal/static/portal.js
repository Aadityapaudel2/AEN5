(function () {
  const runtimeLine = document.getElementById("runtime-line");
  const userLine = document.getElementById("user-line");
  const authBtnGroup = document.getElementById("auth-btn-group");
  const authInstitutionBtn = document.getElementById("auth-institution-btn");
  const logoutBtn = document.getElementById("logout-btn");
  const sendBtn = document.getElementById("send-btn");
  const stopBtn = document.getElementById("stop-btn");
  const clearBtn = document.getElementById("clear-btn");
  const attachBtn = document.getElementById("attach-btn");
  const clearImagesBtn = document.getElementById("clear-images-btn");
  const imageInput = document.getElementById("image-input");
  const imageCount = document.getElementById("image-count");
  const imagePreview = document.getElementById("image-preview");
  const promptInput = document.getElementById("prompt-input");
  const statusBox = document.getElementById("status-box");
  const transcriptEl = document.getElementById("transcript");
  const transcriptScrollEl = document.getElementById("transcript-scroll");
  const reducedMotionQuery = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

  const portalCfg = window.ATHENA_PORTAL || {};
  const hasChatSurface = !!(sendBtn && clearBtn && promptInput && transcriptEl && transcriptScrollEl);

  const state = {
    pathPrefix: portalCfg.pathPrefix || "/AEN5",
    shellMode: portalCfg.shellMode || "browser",
    authProviderLabel: portalCfg.authProviderLabel || "GitHub",
    authProviders: Array.isArray(portalCfg.authProviders) ? portalCfg.authProviders : [],
    institutions: Array.isArray(portalCfg.institutions) ? portalCfg.institutions : [],
    defaultInstitutionKey: portalCfg.defaultInstitutionKey || "",
    authRequired: !!portalCfg.authRequired,
    authenticated: !!portalCfg.authenticated,
    assistantLabel: portalCfg.assistantLabel || "Athena",
    initialHistory: Array.isArray(portalCfg.initialHistory) ? portalCfg.initialHistory : [],
    history: [],
    config: null,
    me: null,
    userDisplayName: "User",
    busy: false,
    currentRequestId: "",
    pendingImages: [],
    reducedMotion: !!(reducedMotionQuery && reducedMotionQuery.matches),
  };

  function setStatus(text) {
    if (!statusBox) return;
    statusBox.textContent = text;
  }

  function setAuthButtons(visible) {
    const institutions = Array.isArray(state.config && state.config.institutions)
      ? state.config.institutions
      : state.institutions;
    const showInstitution = visible && institutions.length > 0;
    if (authInstitutionBtn) authInstitutionBtn.classList.toggle("hidden", !showInstitution);
    if (authBtnGroup) authBtnGroup.classList.toggle("hidden", !showInstitution);
  }

  function scrollBottom() {
    if (!transcriptScrollEl) return;
    transcriptScrollEl.scrollTop = transcriptScrollEl.scrollHeight;
  }

  function textLikelyHasMath(text) {
    const raw = String(text || "");
    if (!raw) return false;
    return /(^|[^\\])\$[^$\n][\s\S]{0,180}?\$/.test(raw) || /\\\([\s\S]{1,180}?\\\)/.test(raw) || /\\\[[\s\S]{1,320}?\\\]/.test(raw);
  }

  function typesetMath(scopeNode) {
    if (!(window.MathJax && typeof window.MathJax.typesetPromise === "function")) return;
    const root = scopeNode || transcriptEl;
    if (!root) return;
    const candidates = [];
    if (root.classList && root.classList.contains("msg-body")) {
      candidates.push(root);
    } else if (root.querySelectorAll) {
      root.querySelectorAll(".msg-body").forEach(function (node) {
        candidates.push(node);
      });
    }
    const targets = candidates.filter(function (node) {
      if (!node) return false;
      const rawText = getRawMessageText(node);
      return textLikelyHasMath(rawText);
    });
    if (!targets.length) return;
    window.MathJax.typesetPromise(targets).catch(function () {
      return;
    });
  }

  function autosizePrompt() {
    if (!promptInput) return;
    const maxPx = 180;
    promptInput.style.height = "auto";
    const next = Math.max(52, Math.min(promptInput.scrollHeight, maxPx));
    promptInput.style.height = String(next) + "px";
  }

  function setBusy(flag) {
    state.busy = !!flag;
    if (sendBtn) sendBtn.disabled = state.busy;
    if (stopBtn) stopBtn.disabled = !state.busy;
    if (clearBtn) clearBtn.disabled = state.busy;
    if (promptInput) promptInput.disabled = state.busy;
    if (attachBtn) attachBtn.disabled = state.busy;
    if (imageInput) imageInput.disabled = state.busy;
    if (clearImagesBtn) clearImagesBtn.disabled = state.busy || state.pendingImages.length === 0;
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

  function getRawMessageText(bodyNode) {
    if (!bodyNode) return "";
    const rawB64 = bodyNode.getAttribute("data-raw-b64");
    if (rawB64) {
      const decoded = decodeRawB64(rawB64);
      if (decoded) return decoded;
    }
    const datasetRaw = bodyNode.dataset ? bodyNode.dataset.rawText : "";
    if (datasetRaw) return datasetRaw;
    return bodyNode.textContent || "";
  }

  function copyFallback(text) {
    const ta = document.createElement("textarea");
    ta.value = String(text || "");
    ta.setAttribute("readonly", "true");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.focus();
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

  async function copyTextToClipboard(text, okMessage) {
    const payload = String(text || "");
    if (!payload) {
      setStatus("Nothing to copy.");
      return false;
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(payload);
        setStatus(okMessage || "Copied.");
        return true;
      }
      const ok = copyFallback(payload);
      setStatus(ok ? okMessage || "Copied." : "Copy failed.");
      return ok;
    } catch (err) {
      const ok = copyFallback(payload);
      setStatus(ok ? okMessage || "Copied." : "Copy failed: " + (err && err.message ? err.message : "unknown error"));
      return ok;
    }
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

  function relabelRenderedUserMessages() {
    if (!transcriptEl) return;
    const label = String(state.userDisplayName || "User").trim() || "User";
    transcriptEl.querySelectorAll(".msg.user .role-pill").forEach(function (pill) {
      let icon = pill.querySelector(".role-icon");
      if (!icon) {
        icon = document.createElement("span");
        icon.className = "role-icon";
        icon.textContent = "??";
        pill.insertBefore(icon, pill.firstChild);
      }
      while (icon.nextSibling) {
        pill.removeChild(icon.nextSibling);
      }
      pill.appendChild(document.createTextNode(label));
    });
  }

  function roleLabel(role) {
    if (role === "user") return String(state.userDisplayName || "User").trim() || "User";
    if (role === "assistant") return state.assistantLabel;
    if (role === "system") return "Portal";
    return "Message";
  }

  function roleIcon(role) {
    if (role === "user") return "\u{1F9D1}";
    if (role === "assistant") return "\u{1F9E0}";
    if (role === "system") return "\u2699\uFE0F";
    return "\u{1F4AC}";
  }

  function makeLiveMessage(role, text, imageUrls) {
    const article = document.createElement("article");
    article.className = "msg " + role + (state.reducedMotion ? "" : " reveal");

    const avatar = document.createElement("aside");
    avatar.className = "avatar";
    avatar.setAttribute("aria-hidden", "true");
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
    copyBtn.title = "Copy raw message";
    copyBtn.setAttribute("aria-label", "Copy raw message");
    copyBtn.textContent = "Copy";
    head.appendChild(copyBtn);

    const body = document.createElement("section");
    body.className = "msg-body";
    body.style.whiteSpace = "pre-wrap";
    body.textContent = text || "";
    body.dataset.rawText = text || "";
    if (Array.isArray(imageUrls) && imageUrls.length > 0) {
      imageUrls.forEach(function (url, idx) {
        if (!url) return;
        const img = document.createElement("img");
        img.loading = "lazy";
        img.decoding = "async";
        img.alt = "attached image " + String(idx + 1);
        img.src = url;
        body.appendChild(document.createElement("br"));
        body.appendChild(img);
      });
    }

    bubble.appendChild(head);
    bubble.appendChild(body);
    article.appendChild(avatar);
    article.appendChild(bubble);
    return { article, body };
  }

  function createStreamWriter(bodyNode) {
    const streamState = {
      active: true,
      queue: "",
      rafId: 0,
      spanCount: 0,
      spanChars: 0,
    };

    function flattenChunks() {
      const flattened = bodyNode.textContent || "";
      bodyNode.textContent = flattened;
      streamState.spanCount = 0;
      streamState.spanChars = 0;
    }

    function appendAnimatedSlice(slice) {
      if (!slice) return;
      const chunk = document.createElement("span");
      chunk.className = "stream-chunk";
      chunk.textContent = slice;
      bodyNode.appendChild(chunk);
      streamState.spanCount += 1;
      streamState.spanChars += slice.length;
      if (streamState.spanCount >= 48 || streamState.spanChars >= 1200) {
        flattenChunks();
      }
    }

    function charsPerFrame() {
      const queued = streamState.queue.length;
      if (queued > 1200) return 72;
      if (queued > 640) return 44;
      if (queued > 260) return 24;
      if (queued > 96) return 12;
      if (queued > 24) return 6;
      return 2;
    }

    function flushFrame() {
      streamState.rafId = 0;
      if (!streamState.active || !streamState.queue) return;
      const take = Math.min(charsPerFrame(), streamState.queue.length);
      const slice = streamState.queue.slice(0, take);
      streamState.queue = streamState.queue.slice(take);
      bodyNode.dataset.rawText = (bodyNode.dataset.rawText || "") + slice;
      appendAnimatedSlice(slice);
      scrollBottom();
      if (streamState.queue) {
        streamState.rafId = window.requestAnimationFrame(flushFrame);
      }
    }

    return {
      push: function (txt) {
        if (!streamState.active) return;
        const chunk = String(txt || "");
        if (!chunk) return;
        streamState.queue += chunk;
        if (!streamState.rafId) {
          streamState.rafId = window.requestAnimationFrame(flushFrame);
        }
      },
      drain: function () {
        if (!streamState.queue && !streamState.rafId) return Promise.resolve();
        return new Promise(function (resolve) {
          const check = function () {
            if (!streamState.queue && !streamState.rafId) {
              resolve();
              return;
            }
            window.setTimeout(check, 16);
          };
          check();
        });
      },
      stop: function () {
        streamState.active = false;
        if (streamState.rafId) {
          window.cancelAnimationFrame(streamState.rafId);
          streamState.rafId = 0;
        }
        streamState.queue = "";
      },
    };
  }

  function applyTranscriptHtml(html) {
    if (!transcriptEl) return;
    transcriptEl.innerHTML = html || "";
    relabelRenderedUserMessages();
    decorateCodeBlocks(transcriptEl);
    scrollBottom();
    typesetMath(transcriptEl);
  }

  function renderPendingImages() {
    if (!imagePreview || !imageCount) return;
    imagePreview.innerHTML = "";
    const count = state.pendingImages.length;
    imageCount.textContent = count === 1 ? "1 image" : String(count) + " images";
    if (clearImagesBtn) clearImagesBtn.disabled = count === 0 || state.busy;
    if (count === 0) {
      imagePreview.style.display = "none";
      return;
    }
    imagePreview.style.display = "flex";
    state.pendingImages.forEach(function (item) {
      const img = document.createElement("img");
      img.className = "thumb";
      img.loading = "lazy";
      img.decoding = "async";
      img.alt = item.name || "attached image";
      img.src = item.data_url;
      imagePreview.appendChild(img);
    });
  }

  function fileToDataUrl(file) {
    return new Promise(function (resolve, reject) {
      const reader = new FileReader();
      reader.onload = function () {
        resolve(String(reader.result || ""));
      };
      reader.onerror = function () {
        reject(new Error("Failed to read image: " + (file && file.name ? file.name : "unknown")));
      };
      reader.readAsDataURL(file);
    });
  }

  async function addImageFiles(fileList) {
    const files = Array.from(fileList || []);
    if (files.length === 0) return;
    const maxImages = 6;
    for (const file of files) {
      if (state.pendingImages.length >= maxImages) {
        setStatus("Image limit reached (" + maxImages + " max per request).");
        break;
      }
      if (!file.type || !file.type.startsWith("image/")) continue;
      if (file.size > 8 * 1024 * 1024) {
        setStatus("Skipped " + file.name + " (over 8MB).");
        continue;
      }
      const dataUrl = await fileToDataUrl(file);
      state.pendingImages.push({
        name: file.name || "image.png",
        content_type: file.type || "image/png",
        data_url: dataUrl,
      });
    }
    renderPendingImages();
  }

  function clearPendingImages() {
    state.pendingImages = [];
    if (imageInput) imageInput.value = "";
    renderPendingImages();
  }

  async function apiGet(path) {
    const res = await fetch(state.pathPrefix + path, { credentials: "same-origin" });
    if (!res.ok) {
      const err = new Error("GET " + path + " failed: " + res.status);
      err.status = res.status;
      throw err;
    }
    return res.json();
  }

  async function apiPost(path, body) {
    const res = await fetch(state.pathPrefix + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(body || {}),
    });
    const payload = await res.json().catch(function () {
      return {};
    });
    if (!res.ok) {
      const message = (payload && payload.detail) || "Request failed.";
      const err = new Error(String(message));
      err.status = res.status;
      throw err;
    }
    return payload;
  }

  function handleAuthFailure() {
    window.location.href = state.pathPrefix;
  }

  async function streamChat(prompt, history, images, requestId, handlers) {
    const res = await fetch(state.pathPrefix + "/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ request_id: requestId || "", prompt: prompt, history: history || [], images: images || [] }),
    });
    if (res.status === 401) {
      handleAuthFailure();
      return null;
    }
    if (!res.ok) {
      let message = "Request failed.";
      try {
        const payload = await res.json();
        message = (payload && payload.detail) || message;
      } catch (_err) {
        message = "Request failed: " + res.status;
      }
      throw new Error(message);
    }
    if (!res.body) throw new Error("Streaming response body not available.");

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let donePayload = null;

    function processEventBlock(block) {
      const raw = (block || "").trim();
      if (!raw) return false;
      const dataLines = raw
        .split(/\r?\n/)
        .map(function (line) {
          return line.trim();
        })
        .filter(function (line) {
          return line.startsWith("data:");
        })
        .map(function (line) {
          return line.slice(5).trim();
        });
      if (dataLines.length === 0) return false;
      const evt = JSON.parse(dataLines.join("\n"));
      if (evt.type === "assistant_delta") {
        handlers.onDelta(evt.text || "");
        return false;
      }
      if (evt.type === "tool_request" || evt.type === "tool_result") {
        if (handlers.onTool) handlers.onTool(evt);
        return false;
      }
      if (evt.type === "status") {
        if (handlers.onStatus) handlers.onStatus(evt.text || "");
        return false;
      }
      if (evt.type === "turn_done") {
        donePayload = evt;
        if (handlers.onDone) handlers.onDone(evt);
        return true;
      }
      if (evt.type === "turn_error") {
        throw new Error(evt.message || "Streaming failed.");
      }
      return false;
    }

    try {
      while (true) {
        const step = await reader.read();
        if (step.done) break;
        buffer += decoder.decode(step.value, { stream: true });
        let sep = buffer.search(/\r?\n\r?\n/);
        while (sep >= 0) {
          const block = buffer.slice(0, sep);
          const sepLen = buffer.slice(sep, sep + 2) === "\r\n" ? 4 : 2;
          buffer = buffer.slice(sep + sepLen);
          if (processEventBlock(block)) {
            try {
              await reader.cancel();
            } catch (_err) {
            }
            return donePayload;
          }
          sep = buffer.search(/\r?\n\r?\n/);
        }
      }
      if (buffer.trim()) {
        processEventBlock(buffer);
      }
      return donePayload;
    } finally {
      try {
        reader.releaseLock();
      } catch (_err) {
      }
    }
  }

  async function sendMessage() {
    if (!hasChatSurface) return;
    const prompt = (promptInput.value || "").trim();
    const outgoingImages = state.pendingImages.slice();
    if ((!prompt && outgoingImages.length === 0) || state.busy) return;

    setBusy(true);
    promptInput.value = "";
    autosizePrompt();
    clearPendingImages();

    const userDisplay = prompt || "Image attached.";
    const imageDataUrls = outgoingImages.map(function (x) {
      return x.data_url;
    });

    const userLive = makeLiveMessage("user", userDisplay, imageDataUrls);
    transcriptEl.appendChild(userLive.article);
    let assistantLive = null;
    let assistantTyper = null;
    let donePayload = null;
    const requestId = (window.crypto && typeof window.crypto.randomUUID === "function")
      ? window.crypto.randomUUID()
      : "req-" + String(Date.now()) + "-" + Math.random().toString(16).slice(2);
    state.currentRequestId = requestId;
    scrollBottom();

    setStatus("Request sent. Waiting for first token...");

    let firstTokenTimer = null;
    let stallInterval = null;
    let lastDeltaAt = Date.now();
    try {
      let sawDelta = false;

      firstTokenTimer = setTimeout(function () {
        if (!sawDelta) {
          setStatus("Model is preparing the first token...");
        }
      }, 3000);

      stallInterval = setInterval(function () {
        if (state.busy && sawDelta && Date.now() - lastDeltaAt > 10000) {
          setStatus("Stream paused briefly. Waiting for more output...");
        }
      }, 1500);

      donePayload = await streamChat(prompt, state.history, outgoingImages, requestId, {
        onDelta: function (txt) {
          sawDelta = true;
          lastDeltaAt = Date.now();
          if (!assistantLive) {
            assistantLive = makeLiveMessage("assistant", "");
            assistantLive.article.classList.add("streaming");
            transcriptEl.appendChild(assistantLive.article);
            assistantTyper = createStreamWriter(assistantLive.body);
            scrollBottom();
          }
          assistantTyper.push(txt);
        },
        onTool: function (evt) {
          const live = makeLiveMessage("system", evt.text || "");
          transcriptEl.appendChild(live.article);
          scrollBottom();
        },
        onStatus: function (txt) {
          if (txt) setStatus(txt);
        },
      });

      if (!donePayload) {
        throw new Error("Stream disconnected before completion.");
      }
      if (assistantTyper) {
        await assistantTyper.drain();
      }
      state.history = donePayload.history || [];
      applyTranscriptHtml(donePayload.transcript_html || "");
      setStatus(donePayload.model_loaded ? "Athena is ready to keep teaching, explaining, and helping." : "Response received.");
    } catch (err) {
      if (assistantTyper) assistantTyper.stop();
      if (donePayload) {
        try {
          state.history = donePayload.history || state.history;
          applyTranscriptHtml(donePayload.transcript_html || "");
          setStatus("Response received. A client-side render issue occurred after completion: " + err.message);
        } catch (_renderErr) {
          setStatus("Response completed, but the browser hit a render issue: " + err.message);
        }
      } else {
        if (!assistantLive) {
          assistantLive = makeLiveMessage("assistant", "Request failed.");
          transcriptEl.appendChild(assistantLive.article);
        } else {
          assistantLive.body.textContent = "Request failed.";
          assistantLive.body.dataset.rawText = "Request failed.";
        }
        setStatus("Request failed: " + err.message);
      }
    } finally {
      if (assistantTyper) assistantTyper.stop();
      if (firstTokenTimer) clearTimeout(firstTokenTimer);
      if (stallInterval) clearInterval(stallInterval);
      state.currentRequestId = "";
      setBusy(false);
      if (promptInput) promptInput.focus();
    }
  }

  async function stopGeneration() {
    if (!state.busy || !state.currentRequestId) return;
    setStatus("Stopping generation...");
    try {
      const payload = await apiPost("/api/chat/stop", { request_id: state.currentRequestId });
      if (!payload || !payload.stopped) {
        setStatus("No active generation was found to stop.");
        return;
      }
      setStatus("Stop requested. Waiting for the current response to close cleanly...");
    } catch (err) {
      setStatus("Stop request failed: " + err.message);
    }
  }

  async function clearConversation() {
    if (!hasChatSurface) return;
    try {
      await apiPost("/api/chat/reset", {});
      state.history = [];
      state.currentRequestId = "";
      clearPendingImages();
      applyTranscriptHtml("");
      setStatus("Conversation and short-lived continuity cleared. Course context remains available.");
    } catch (err) {
      setStatus("Reset failed: " + err.message);
    }
  }

  async function bootstrap() {
    if (!hasChatSurface) {
      typesetMath(transcriptEl);
      return;
    }
    try {
      state.config = await apiGet("/api/config");
      if (state.config && state.config.assistant_label) {
        state.assistantLabel = state.config.assistant_label;
      }
      if (runtimeLine) {
        runtimeLine.textContent = "Athena is ready to teach, explain, and support curriculum-aligned learning.";
        runtimeLine.title = "Public NeohmLabs AEN browser surface";
      }
      state.history = Array.isArray(state.initialHistory) ? state.initialHistory.slice() : [];

      if (state.config.auth_required) {
        try {
          const me = await apiGet("/api/me");
          state.me = me.user || null;
        } catch (err) {
          if (err.status === 401) {
            handleAuthFailure();
            return;
          }
          throw err;
        }
      } else {
        if (logoutBtn) logoutBtn.style.display = "none";
        setAuthButtons(false);
      }

      if (state.me) {
        const display = state.me.name || state.me.email || "signed in";
        state.userDisplayName = display;
        let suffix = "";
        if (state.me.is_guest && state.config && state.config.guest_prompt_limit) {
          const used = Number(state.config.guest_prompt_count || 0);
          const lim = Number(state.config.guest_prompt_limit || 0);
          if (lim > 0) {
            suffix = " (guest " + String(used) + "/" + String(lim) + ")";
          }
        }
        if (userLine) userLine.textContent = "User: " + display + suffix;
        if (state.me.is_guest) {
          setAuthButtons(true);
          if (logoutBtn) logoutBtn.textContent = "Leave Guest";
        } else {
          setAuthButtons(false);
          if (logoutBtn) logoutBtn.textContent = "Logout";
        }
      } else {
        state.userDisplayName = state.shellMode === "desktop" ? "local" : "anonymous";
        if (userLine) userLine.textContent = state.shellMode === "desktop" ? "Local desktop session" : "User: anonymous";
      }

      relabelRenderedUserMessages();
      if (state.config.model_load_error) {
        setStatus("Model load warning: " + state.config.model_load_error);
      } else {
        setStatus(state.history.length ? "Conversation history and learner memory restored." : "Ready to help.");
      }
    } catch (err) {
      if (runtimeLine) runtimeLine.textContent = "Failed to load portal config.";
      setStatus("Bootstrap failed: " + err.message);
      return;
    }

    if (sendBtn) sendBtn.disabled = false;
    typesetMath(transcriptEl);
  }

  async function logout() {
    try {
      await apiPost("/auth/logout", {});
    } catch (_err) {
    }
    window.location.href = state.pathPrefix;
  }

  if (sendBtn) sendBtn.addEventListener("click", sendMessage);
  if (stopBtn) stopBtn.addEventListener("click", stopGeneration);
  if (clearBtn) clearBtn.addEventListener("click", clearConversation);
  if (logoutBtn) logoutBtn.addEventListener("click", logout);

  if (transcriptEl) {
    transcriptEl.addEventListener("click", async function (event) {
      const target = event.target;
      if (!target || !target.classList) return;
      if (target.classList.contains("copy-msg-btn")) {
        const msg = target.closest(".msg");
        const body = msg ? msg.querySelector(".msg-body") : null;
        await copyTextToClipboard(getRawMessageText(body), "Message copied.");
        return;
      }
      if (target.classList.contains("copy-code-btn")) {
        const pre = target.closest("pre");
        const code = pre ? pre.querySelector("code") : null;
        await copyTextToClipboard(code ? code.textContent || "" : "", "Code copied.");
      }
    });
  }

  if (attachBtn && imageInput) {
    attachBtn.addEventListener("click", function () {
      if (state.busy) return;
      imageInput.click();
    });
    imageInput.addEventListener("change", async function (event) {
      const files = event.target && event.target.files ? event.target.files : [];
      try {
        await addImageFiles(files);
      } catch (err) {
        setStatus("Image attach failed: " + err.message);
      } finally {
        imageInput.value = "";
      }
    });
  }

  if (clearImagesBtn) {
    clearImagesBtn.addEventListener("click", function () {
      clearPendingImages();
      setStatus("Pending images cleared.");
    });
  }

  if (promptInput) {
    promptInput.addEventListener("keydown", function (event) {
      if (event.isComposing) return;
      if ((event.key === "Enter" || event.key === "NumpadEnter") && !event.shiftKey) {
        event.preventDefault();
        if (!state.busy) sendMessage();
      }
    });
    promptInput.addEventListener("paste", async function (event) {
      if (!event.clipboardData || state.busy) return;
      const files = [];
      const items = Array.from(event.clipboardData.items || []);
      items.forEach(function (item) {
        if (item.kind === "file") {
          const file = item.getAsFile();
          if (file) files.push(file);
        }
      });
      if (files.length === 0) return;
      event.preventDefault();
      try {
        await addImageFiles(files);
        setStatus("Image pasted from clipboard.");
      } catch (err) {
        setStatus("Clipboard image paste failed: " + err.message);
      }
    });
    promptInput.addEventListener("input", autosizePrompt);
  }

  bootstrap();
  autosizePrompt();
  renderPendingImages();
  decorateCodeBlocks(transcriptEl);
})();

