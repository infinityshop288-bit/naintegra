/** Data da última atualização do acervo (exibida na sidebar). */
(function () {
  const cfg = window.LEX_CONFIG;

  async function fetchLastContentUpdate() {
    try {
      const client = window.LexAuth.getClient();
      const { data } = await client
        .schema(cfg.lexSchema)
        .from("content_metadata")
        .select("value")
        .eq("key", "last_content_update")
        .maybeSingle();
      if (data?.value) return new Date(data.value);
    } catch (e) {
      console.warn(e);
    }
    if (cfg.lastContentUpdate) return new Date(cfg.lastContentUpdate);
    return null;
  }

  function formatDatePt(d) {
    if (!d) return "—";
    return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
  }

  async function renderSidebarUpdate() {
    const el = document.getElementById("sidebar-last-update");
    if (!el) return;
    const d = await fetchLastContentUpdate();
    el.textContent = d ? `Acervo atualizado em ${formatDatePt(d)}` : "";
  }

  window.LexContentUpdate = {
    fetchLastContentUpdate,
    formatDatePt,
    renderSidebarUpdate,
  };
})();
