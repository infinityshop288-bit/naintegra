/** Proteção de conteúdo — reduz cópia casual e reforça licença pessoal. */
(function () {
  const BLOCK_KEYS = new Set(["c", "C", "p", "P", "s", "S", "u", "U", "a", "A"]);

  function applyWatermark() {
    let layer = document.getElementById("lex-watermark");
    if (!layer) {
      layer = document.createElement("div");
      layer.id = "lex-watermark";
      layer.className = "lex-watermark";
      layer.setAttribute("aria-hidden", "true");
      document.body.appendChild(layer);
    }
    window.LexAuth?.getUser?.().then((u) => {
      const label = u?.email || "NaIntegra Lex";
      layer.textContent = `${label} · uso pessoal · cópia proibida`.repeat(40);
    });
  }

  function isProtectedTarget(node) {
    return node?.closest?.(".lex-protected, .reader-body, .flash-face, .flash-face-body, .q-card");
  }

  function onContextMenu(e) {
    if (isProtectedTarget(e.target)) e.preventDefault();
  }

  function onKeyDown(e) {
    if (!isProtectedTarget(e.target)) return;
    if (e.ctrlKey || e.metaKey) {
      if (BLOCK_KEYS.has(e.key)) e.preventDefault();
    }
  }

  function onCopy(e) {
    if (isProtectedTarget(e.target)) {
      e.preventDefault();
      flashNotice();
    }
  }

  function onDragStart(e) {
    if (isProtectedTarget(e.target)) e.preventDefault();
  }

  let noticeTimer;
  function flashNotice() {
    let n = document.getElementById("lex-copy-notice");
    if (!n) {
      n = document.createElement("div");
      n.id = "lex-copy-notice";
      n.className = "lex-copy-notice";
      n.textContent = "Conteúdo protegido — uso pessoal apenas";
      document.body.appendChild(n);
    }
    n.classList.add("visible");
    clearTimeout(noticeTimer);
    noticeTimer = setTimeout(() => n.classList.remove("visible"), 2200);
  }

  function markProtected(root) {
    (root || document).querySelectorAll(".reader-body, .flash-face, .flash-face-body, .q-card, .q-alt-list").forEach((el) => {
      el.classList.add("lex-protected");
    });
  }

  function init() {
    document.addEventListener("contextmenu", onContextMenu);
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("copy", onCopy);
    document.addEventListener("dragstart", onDragStart);
    applyWatermark();
    markProtected(document);
    const observer = new MutationObserver(() => markProtected(document));
    observer.observe(document.getElementById("app") || document.body, { childList: true, subtree: true });
  }

  window.LexProtect = { init, markProtected, applyWatermark };
})();
