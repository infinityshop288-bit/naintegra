(function () {
  const cfg = window.DELEGADO_CONFIG;
  let client = null;
  const listeners = new Set();

  function getClient() {
    if (!client && window.supabase?.createClient) {
      client = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: false,
          flowType: "pkce",
          storage: window.sessionStorage,
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

  function onAuthStateChange(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }

  function assertAllowedEmail(email) {
    const allowed = (cfg.allowedEmail || "").toLowerCase();
    if (allowed && email?.toLowerCase() !== allowed) {
      throw new Error("Acesso restrito à conta " + cfg.allowedEmail);
    }
  }

  async function signInWithPassword(email, password) {
    assertAllowedEmail(email);
    const c = getClient();
    const { data, error } = await c.auth.signInWithPassword({ email, password });
    if (error) throw error;
    assertAllowedEmail(data.session?.user?.email);
    return data.session;
  }

  async function signOut() {
    const c = getClient();
    if (!c) return;
    await c.auth.signOut();
  }

  async function finishOAuthCallback() {
    const c = getClient();
    const { data, error } = await c.auth.exchangeCodeForSession(window.location.href);
    if (error) throw error;
    assertAllowedEmail(data.session?.user?.email);
    window.location.replace("./index.html");
  }

  async function getAccessToken() {
    const session = await getSession();
    return session?.access_token ?? null;
  }

  window.DelegadoAuth = {
    getClient,
    getSession,
    onAuthStateChange,
    signInWithPassword,
    signOut,
    finishOAuthCallback,
    getAccessToken,
    assertAllowedEmail,
  };
})();
