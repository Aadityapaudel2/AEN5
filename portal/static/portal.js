(function () {
  const runtimeLine = document.getElementById("runtime-line");
  const sendBtn = document.getElementById("send-btn");
  const clearBtn = document.getElementById("clear-btn");
  const promptInput = document.getElementById("prompt-input");
  const statusBox = document.getElementById("status-box");
  const transcriptEl = document.getElementById("transcript");
  const transcriptScrollEl = document.getElementById("transcript-scroll");
  const thinkingToggle = document.getElementById("thinking-toggle");
  const showThoughtsToggle = document.getElementById("show-thoughts-toggle");

  const state = {
    pathPrefix: (window.ATHENA_PORTAL && window.ATHENA_PORTAL.pathPrefix) || "/AthenaV5",
    history: [],
    config: null,
    busy: false,
  };

  function setStatus(text) {
    statusBox.textContent = text;
  }

  function scrollBottom() {
    if (!transcriptScrollEl) {
      return;
    }
    transcriptScrollEl.scrollTop = transcriptScrollEl.scrollHeight;
  }

  function applyTranscriptHtml(html) {
    transcriptEl.innerHTML = html || "";
    scrollBottom();
  }

  async function apiGet(path) {
    const res = await fetch(state.pathPrefix + path, { credentials: "same-origin" });
    if (!res.ok) {
      throw new Error("GET " + path + " failed: " + res.status);
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

  function setBusy(flag) {
    state.busy = !!flag;
    sendBtn.disabled = state.busy;
    clearBtn.disabled = state.busy;
    promptInput.disabled = state.busy;
    thinkingToggle.disabled = state.busy;
    showThoughtsToggle.disabled = state.busy;
  }

  async function sendMessage() {
    const prompt = (promptInput.value || "").trim();
    if (!prompt) {
      return;
    }

    setBusy(true);
    setStatus("Sending...");
    try {
      const payload = await apiPost("/api/chat", {
        prompt: prompt,
        history: state.history,
        enable_thinking: !!thinkingToggle.checked,
        show_thoughts: !!showThoughtsToggle.checked,
      });
      state.history = payload.history || [];
      applyTranscriptHtml(payload.transcript_html || "");
      const modeText = payload.smoke_mode
        ? "Smoke mode response received."
        : payload.model_loaded
          ? "Model response received."
          : "Response received.";
      setStatus(modeText);
      promptInput.value = "";
      promptInput.focus();
    } catch (err) {
      setStatus("Request failed: " + err.message);
    } finally {
      setBusy(false);
    }
  }

  function clearConversation() {
    state.history = [];
    applyTranscriptHtml("");
    setStatus("Conversation cleared.");
  }

  async function bootstrap() {
    try {
      state.config = await apiGet("/api/config");
      const smoke = state.config.smoke_mode ? "on" : "off";
      const loaded = state.config.model_loaded ? "loaded" : "not loaded";
      runtimeLine.textContent =
        "Path " + state.config.path_prefix + " | smoke " + smoke + " | model " + loaded;
      if (state.config.model_load_error) {
        setStatus("Model load warning: " + state.config.model_load_error);
      } else if (state.config.smoke_mode) {
        setStatus("Smoke mode active. UI and routing are live.");
      } else {
        setStatus("Ready.");
      }
    } catch (err) {
      runtimeLine.textContent = "Failed to load portal config.";
      setStatus("Bootstrap failed: " + err.message);
      return;
    }
    sendBtn.disabled = false;
  }

  sendBtn.addEventListener("click", sendMessage);
  clearBtn.addEventListener("click", clearConversation);
  promptInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!state.busy) {
        sendMessage();
      }
    }
  });

  bootstrap();
})();
