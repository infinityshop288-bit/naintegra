/** Autenticação NaIntegra Lex — e-mail, Google, Apple e recuperação de senha. */
(function () {
  const cfg = window.LEX_CONFIG;
  let client = null;
  const listeners = new Set();

  const STORAGE_OAUTH_RETURN = "lex_oauth_return_path";
  const OAUTH_CALLBACK_FILE = "auth-callback.html";
  const NAINTEGRA_HOSTS = new Set(["naintegracursos.com.br", "www.naintegracursos.com.br"]);

  function isNaIntegraHost(hostname) {
    return NAINTEGRA_HOSTS.has(String(hostname || window.location.hostname).toLowerCase());
  }

  function normalizeOrigin(origin) {
    return String(origin || "").replace(/\/$/, "").toLowerCase();
  }

  function isAllowedNaIntegraOrigin(origin) {
    const normalized = normalizeOrigin(origin);
    return (
      normalized === normalizeOrigin(siteOrigin()) ||
      normalized === normalizeOrigin(window.location.origin) ||
      normalized === "https://naintegracursos.com.br" ||
      normalized === "https://www.naintegracursos.com.br"
    );
  }

  /** PKCE exige mesma origem no início do OAuth e no callback. */
  function ensureCanonicalOrigin() {
    const canonical = siteOrigin();
    if (!canonical || window.location.protocol === "file:" || !isNaIntegraHost()) return false;
    if (window.location.pathname.includes(OAUTH_CALLBACK_FILE)) return false;
    if (new URL(window.location.href).searchParams.has("code")) return false;
    if (normalizeOrigin(window.location.origin) === normalizeOrigin(canonical)) return false;
    window.location.replace(
      `${canonical}${window.location.pathname}${window.location.search}${window.location.hash}`,
    );
    return true;
  }

  function siteOrigin() {
    const fromCfg = cfg.siteOrigin?.trim().replace(/\/$/, "");
    if (fromCfg) return fromCfg;
    return window.location.origin;
  }

  function lexPublicBase() {
    const fromCfg = cfg.lexPublicPath?.trim();
    if (fromCfg) {
      const path = fromCfg.startsWith("/") ? fromCfg : `/${fromCfg}`;
      return path.endsWith("/") ? path : `${path}/`;
    }
    const path = window.location.pathname || "/";
    const idx = path.indexOf("/lex");
    if (idx >= 0) {
      const rest = path.slice(idx, path.lastIndexOf("/") + 1);
      return rest.endsWith("/") ? rest : `${rest}/`;
    }
    return path.endsWith("/") ? path : `${path.replace(/\/[^/]*$/, "/")}`;
  }

  /** Callback na mesma origem da aba (PKCE). Fallback: config canônica. */
  function oauthRedirectUrl() {
    if (isNaIntegraHost()) {
      return `${window.location.origin}${lexPublicBase()}${OAUTH_CALLBACK_FILE}`;
    }
    const explicit = cfg.oauthCallbackUrl?.trim();
    if (explicit) return explicit;
    return `${siteOrigin()}${lexPublicBase()}${OAUTH_CALLBACK_FILE}`;
  }

  function redirectUrl() {
    return `${siteOrigin()}${lexPublicBase()}index.html`;
  }

  function lexHomeUrl() {
    return `${siteOrigin()}${lexPublicBase()}index.html#/`;
  }

  const BLOCKED_OAUTH_ORIGINS = ["https://voltgo.com.br", "https://www.voltgo.com.br"];

  function isBlockedOAuthOrigin(origin) {
    if (!origin) return false;
    const normalized = origin.replace(/\/$/, "").toLowerCase();
    return BLOCKED_OAUTH_ORIGINS.some((blocked) => normalized === blocked.replace(/\/$/, "").toLowerCase());
  }

  function resolveOAuthReturnTarget(returnPath) {
    const home = lexHomeUrl();
    const allowedOrigin = siteOrigin();
    if (!returnPath) return home;

    if (returnPath.includes("/auth/")) {
      return home;
    }

    if (returnPath.startsWith("http")) {
      try {
        const parsed = new URL(returnPath);
        if (isBlockedOAuthOrigin(parsed.origin)) return home;
        if (!isAllowedNaIntegraOrigin(parsed.origin)) return home;
        return returnPath;
      } catch {
        return home;
      }
    }

    if (returnPath.startsWith("/")) {
      return `${allowedOrigin}${returnPath}`;
    }

    if (returnPath.startsWith("./")) {
      return `${allowedOrigin}${lexPublicBase()}${returnPath.slice(2)}`;
    }

    return `${allowedOrigin}${lexPublicBase()}${returnPath.replace(/^\//, "")}`;
  }

  function getClient() {
    if (!client && window.supabase?.createClient) {
      const onOAuthCallback = window.location.pathname.includes(OAUTH_CALLBACK_FILE);
      client = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: !onOAuthCallback,
          flowType: "pkce",
          storage: window.localStorage,
        },
      });
      client.auth.onAuthStateChange((_event, session) => {
        listeners.forEach((fn) => {
          try {
            fn(session);
          } catch (err) {
            console.error(err);
          }
        });
      });
    }
    return client;
  }

  async function getSession() {
    const c = getClient();
    if (!c) return null;
    const { data, error } = await c.auth.getSession();
    if (error) throw error;
    return data.session;
  }

  async function getUser() {
    const session = await getSession();
    return session?.user ?? null;
  }

  function onAuthStateChange(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }

  async function signInWithPassword(email, password) {
    const { data, error } = await getClient().auth.signInWithPassword({ email, password });
    if (error) throw error;
    return data;
  }

  async function signUp(email, password) {
    const { data, error } = await getClient().auth.signUp({
      email,
      password,
      options: { emailRedirectTo: oauthRedirectUrl() },
    });
    if (error) throw error;
    return data;
  }

  async function signOut() {
    const { error } = await getClient().auth.signOut();
    if (error) throw error;
  }

  async function resetPassword(email) {
    const res = await fetch(`${cfg.supabaseUrl}/functions/v1/auth-password-recovery`, {
      method: "POST",
      headers: {
        apikey: cfg.supabaseAnonKey,
        "Content-Type": "application/json",
        Authorization: `Bearer ${cfg.supabaseAnonKey}`,
      },
      body: JSON.stringify({
        email,
        redirectTo: `${redirectUrl()}#/auth/reset-password`,
        product: "lex",
      }),
    });
    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error("Resposta inválida do servidor de e-mail");
    }
    if (!res.ok || data.error) throw new Error(data.error || "Erro ao enviar e-mail de recuperação");
    return data;
  }

  async function updatePassword(password) {
    const { data, error } = await getClient().auth.updateUser({ password });
    if (error) throw error;
    return data;
  }

  function storeOAuthReturnPath(returnPath) {
    sessionStorage.setItem(STORAGE_OAUTH_RETURN, returnPath);
    try {
      localStorage.setItem(STORAGE_OAUTH_RETURN, returnPath);
    } catch (_) {}
  }

  function readOAuthReturnPath() {
    return sessionStorage.getItem(STORAGE_OAUTH_RETURN) || localStorage.getItem(STORAGE_OAUTH_RETURN) || "";
  }

  function clearOAuthReturnPath() {
    sessionStorage.removeItem(STORAGE_OAUTH_RETURN);
    try {
      localStorage.removeItem(STORAGE_OAUTH_RETURN);
    } catch (_) {}
  }

  async function signInWithOAuth(provider) {
    if (ensureCanonicalOrigin()) return;

    const hash = window.location.hash || "#/";
    const safeHash = hash.includes("/auth/") ? "#/" : hash;
    const returnPath = `${lexPublicBase()}index.html${safeHash}`;
    storeOAuthReturnPath(returnPath);

    const options = {
      redirectTo: oauthRedirectUrl(),
      skipBrowserRedirect: false,
    };

    if (provider === "google") {
      options.queryParams = { prompt: "select_account" };
    }
    if (provider === "apple") {
      options.scopes = "name email";
    }

    const { data, error } = await getClient().auth.signInWithOAuth({
      provider,
      options,
    });
    if (error) throw error;
    return data;
  }

  function userLabel(user) {
    if (!user) return "";
    return user.user_metadata?.full_name || user.email?.split("@")[0] || "Conta";
  }

  window.LexAuth = {
    getClient,
    getSession,
    getUser,
    onAuthStateChange,
    signInWithPassword,
    signUp,
    signOut,
    resetPassword,
    updatePassword,
    signInWithOAuth,
    userLabel,
    redirectUrl,
    oauthRedirectUrl,
    lexHomeUrl,
    resolveOAuthReturnTarget,
    readOAuthReturnPath,
    clearOAuthReturnPath,
    ensureCanonicalOrigin,
  };

  ensureCanonicalOrigin();
})();
