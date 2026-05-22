/** Autenticação NaIntegra Lex — e-mail, Google, Apple e recuperação de senha. */
(function () {
  const cfg = window.LEX_CONFIG;
  let client = null;
  const listeners = new Set();

  const STORAGE_OAUTH_RETURN = "lex_oauth_return_path";
  const OAUTH_CALLBACK_FILE = "auth-callback.html";

  function lexBasePath() {
    const path = window.location.pathname || "/";
    const idx = path.indexOf("/lex");
    if (idx >= 0) {
      const rest = path.slice(idx, path.lastIndexOf("/") + 1);
      return rest.endsWith("/") ? rest : `${rest}/`;
    }
    return path.endsWith("/") ? path : `${path.replace(/\/[^/]*$/, "/")}`;
  }

  /** URL estável para PKCE — deve constar em Supabase → Authentication → Redirect URLs. */
  function oauthRedirectUrl() {
    const base = lexBasePath();
    return `${window.location.origin}${base}${OAUTH_CALLBACK_FILE}`;
  }

  function redirectUrl() {
    return `${window.location.origin}${window.location.pathname}`;
  }

  function getClient() {
    if (!client && window.supabase?.createClient) {
      client = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
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
    const { data, error } = await getClient().auth.resetPasswordForEmail(email, {
      redirectTo: `${redirectUrl()}#/auth/reset-password`,
    });
    if (error) throw error;
    return data;
  }

  async function updatePassword(password) {
    const { data, error } = await getClient().auth.updateUser({ password });
    if (error) throw error;
    return data;
  }

  async function signInWithOAuth(provider) {
    const returnPath = `${window.location.pathname}${window.location.search}${window.location.hash || "#/"}`;
    sessionStorage.setItem(STORAGE_OAUTH_RETURN, returnPath);

    const options = {
      redirectTo: oauthRedirectUrl(),
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
  };
})();
