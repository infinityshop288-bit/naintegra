/** OAuth nativo (SFSafariViewController + Sign in with Apple) para Capacitor. */
(function () {
  const NATIVE_OAUTH_SCHEME = "NaIntegraLex://auth-callback";
  let oauthListenerReady = false;

  function capPlugin(name) {
    return window.Capacitor?.Plugins?.[name] || null;
  }

  function isNative() {
    return window.LexPlatform?.isCapacitor?.() ?? false;
  }

  function isIOS() {
    return window.LexPlatform?.isIOS?.() ?? false;
  }

  function isIPad() {
    const ua = navigator.userAgent || "";
    return (
      /iPad/i.test(ua) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
    );
  }

  function parseOAuthCallbackUrl(rawUrl) {
    const normalized = String(rawUrl || "").replace(/^NaIntegraLex:\/\//, "https://callback.local/");
    try {
      return new URL(normalized);
    } catch {
      return null;
    }
  }

  async function finishOAuthFromUrl(rawUrl) {
    const parsed = parseOAuthCallbackUrl(rawUrl);
    if (!parsed) return false;

    const callbackHint =
      parsed.pathname.includes("auth-callback") ||
      parsed.hostname === "callback.local" ||
      String(rawUrl || "").startsWith("NaIntegraLex://");
    if (!callbackHint) return false;

    const Browser = capPlugin("Browser");
    try {
      await Browser?.close?.();
    } catch (_) {
      /* ignore */
    }

    const oauthErr =
      parsed.searchParams.get("error_description") || parsed.searchParams.get("error");
    if (oauthErr) {
      const msg = decodeURIComponent(oauthErr.replace(/\+/g, " "));
      window.LexAuthUI?.open?.("login", msg);
      return true;
    }

    const code = parsed.searchParams.get("code");
    if (!code) return false;

    const { data, error } = await window.LexAuth.getClient().auth.exchangeCodeForSession(code);
    if (error) throw error;
    if (!data.session?.user) throw new Error("Sessão não criada após login");

    const returnPath = window.LexAuth.readOAuthReturnPath();
    window.LexAuth.clearOAuthReturnPath();
    window.location.replace(window.LexAuth.resolveOAuthReturnTarget(returnPath));
    return true;
  }

  async function ensureOAuthListener() {
    if (oauthListenerReady || !isNative()) return;
    const App = capPlugin("App");
    if (!App?.addListener) return;

    await App.addListener("appUrlOpen", async (event) => {
      try {
        await finishOAuthFromUrl(event?.url);
      } catch (err) {
        console.error("Lex native OAuth:", err);
        window.LexAuthUI?.open?.("login", err.message || "Erro ao concluir login");
      }
    });
    oauthListenerReady = true;
  }

  async function signInWithAppleNative() {
    const AppleSignIn = capPlugin("SignInWithApple");
    if (!AppleSignIn?.authorize) {
      throw new Error("Entrar com Apple não está disponível neste dispositivo.");
    }

    const result = await AppleSignIn.authorize({
      clientId: "br.com.naintegracursos.lex",
      redirectURI: window.LexAuth.oauthRedirectUrl(),
      scopes: "email name",
    });

    const identityToken = result?.response?.identityToken;
    if (!identityToken) throw new Error("Token Apple inválido. Tente novamente.");

    const { data, error } = await window.LexAuth.getClient().auth.signInWithIdToken({
      provider: "apple",
      token: identityToken,
    });
    if (error) throw error;
    return data;
  }

  async function signInWithOAuthNative(provider) {
    await ensureOAuthListener();

    if (provider === "apple" && isIOS()) {
      const hash = window.location.hash || "#/";
      const safeHash = hash.includes("/auth/") ? "#/" : hash;
      const base = window.LEX_CONFIG?.lexPublicPath || "/lex/";
      const normalizedBase = base.startsWith("/") ? base : `/${base}`;
      const publicBase = normalizedBase.endsWith("/") ? normalizedBase : `${normalizedBase}/`;
      window.LexAuth.storeOAuthReturnPath(`${publicBase}index.html${safeHash}`);

      const data = await signInWithAppleNative();
      const returnPath = window.LexAuth.readOAuthReturnPath();
      window.LexAuth.clearOAuthReturnPath();
      if (returnPath) {
        window.location.replace(window.LexAuth.resolveOAuthReturnTarget(returnPath));
      }
      return data;
    }

    const hash = window.location.hash || "#/";
    const safeHash = hash.includes("/auth/") ? "#/" : hash;
    const base = window.LEX_CONFIG?.lexPublicPath || "/lex/";
    const normalizedBase = base.startsWith("/") ? base : `/${base}`;
    const publicBase = normalizedBase.endsWith("/") ? normalizedBase : `${normalizedBase}/`;
    window.LexAuth.storeOAuthReturnPath(`${publicBase}index.html${safeHash}`);

    const options = {
      redirectTo: NATIVE_OAUTH_SCHEME,
      skipBrowserRedirect: true,
    };
    if (provider === "google") {
      options.queryParams = { prompt: "select_account" };
    }
    if (provider === "apple") {
      options.scopes = "name email";
    }

    const { data, error } = await window.LexAuth.getClient().auth.signInWithOAuth({
      provider,
      options,
    });
    if (error) throw error;
    if (!data?.url) throw new Error("URL de login indisponível");

    const Browser = capPlugin("Browser");
    if (!Browser?.open) {
      throw new Error("Navegador in-app indisponível. Atualize o app.");
    }

    await Browser.open({
      url: data.url,
      presentationStyle: isIPad() ? "popover" : "fullscreen",
    });
    return data;
  }

  if (isNative()) {
    ensureOAuthListener().catch((err) => console.warn("Lex native bridge init:", err));
  }

  window.LexNativeBridge = {
    isNative,
    isIOS,
    ensureOAuthListener,
    signInWithOAuthNative,
    finishOAuthFromUrl,
  };
})();
