(function () {
  const transcriptEl = document.getElementById("transcript");
  const transcriptScrollEl = document.getElementById("transcript-scroll");
  let mathTimer = null;
  let lastTypesetTarget = null;

  function scheduleMathTypeset() {
    if (mathTimer) {
      clearTimeout(mathTimer);
      mathTimer = null;
    }
    mathTimer = setTimeout(() => {
      if (window.MathJax && window.MathJax.typesetPromise) {
        const target = lastTypesetTarget || transcriptEl;
        window.MathJax.typesetPromise([target]).catch(() => {});
      }
    }, 40);
  }

  function scrollBottom() {
    if (!transcriptScrollEl) {
      window.scrollTo(0, document.body.scrollHeight);
      return;
    }
    transcriptScrollEl.scrollTop = transcriptScrollEl.scrollHeight;
  }

  function latestMathScope() {
    if (!transcriptEl || !transcriptEl.lastElementChild) {
      return transcriptEl;
    }
    const node = transcriptEl.lastElementChild.querySelector(".msg-body");
    return node || transcriptEl.lastElementChild;
  }

  function updateLatestAssistantBody(html, forceTypeset) {
    if (!transcriptEl) {
      return;
    }
    const bodies = transcriptEl.querySelectorAll(".msg.assistant .msg-body");
    if (!bodies.length) {
      return;
    }
    const body = bodies[bodies.length - 1];
    const nextHtml = html || "";
    const unchanged = body.innerHTML === nextHtml;
    if (!unchanged) {
      body.innerHTML = nextHtml;
    }
    lastTypesetTarget = body;
    // Avoid LaTeX flicker during streaming: only typeset on explicit finalization.
    if (forceTypeset) {
      scheduleMathTypeset();
    }
    if (!unchanged || forceTypeset) {
      scrollBottom();
    }
  }

  window.AthenaUI = {
    setTranscriptHtml(html) {
      transcriptEl.innerHTML = html || "";
      lastTypesetTarget = latestMathScope();
      scheduleMathTypeset();
      scrollBottom();
    },
    updateLatestAssistantBody(html, forceTypeset) {
      updateLatestAssistantBody(html, !!forceTypeset);
    },
    notifyMathjaxMissing() {
      // Non-fatal: keep plain text/markdown display if MathJax bundle missing.
      console.warn("MathJax assets not found. Rendering without TeX typesetting.");
    },
  };

  // Probe after startup to detect missing local bundle.
  setTimeout(() => {
    if (!window.MathJax || !window.MathJax.typesetPromise) {
      if (window.AthenaUI && window.AthenaUI.notifyMathjaxMissing) {
        window.AthenaUI.notifyMathjaxMissing();
      }
    }
  }, 500);
})();
