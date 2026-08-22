/** Detecção de plataforma (web, iOS nativo, Android nativo). */
(function () {
  function cap() {
    return window.Capacitor;
  }

  function isCapacitor() {
    return Boolean(cap()?.isNativePlatform?.());
  }

  function platform() {
    if (!isCapacitor()) return "web";
    return cap().getPlatform?.() || "web";
  }

  function isIOS() {
    return platform() === "ios";
  }

  function isAndroid() {
    return platform() === "android";
  }

  function isWeb() {
    return !isCapacitor();
  }

  function showPlayStorePrompts() {
    return isAndroid() || isWeb();
  }

  function showAppStorePrompts() {
    return isIOS();
  }

  function requiresAppleIAP() {
    return isIOS();
  }

  function storeReviewUrl() {
    if (isIOS()) {
      return (
        window.LEX_CONFIG?.appStoreUrl ||
        "https://apps.apple.com/app/naintegra-lex"
      );
    }
    return (
      window.LEX_CONFIG?.playStoreUrl ||
      "https://play.google.com/store/apps/details?id=br.com.naintegracursos.lex"
    );
  }

  function storeReviewLabel() {
    return isIOS() ? "App Store" : "Google Play";
  }

  window.LexPlatform = {
    isCapacitor,
    isIOS,
    isAndroid,
    isWeb,
    platform,
    showPlayStorePrompts,
    showAppStorePrompts,
    requiresAppleIAP,
    storeReviewUrl,
    storeReviewLabel,
  };
})();
