import type { CapacitorConfig } from "@capacitor/cli";

/**
 * NaIntegra Lex — Capacitor.
 * Padrão loja: carrega https://www.naintegracursos.com.br/lex/ (OAuth e conteúdo atualizado).
 * Empacotado local: LEX_MOBILE_USE_BUNDLED=1 npm run build
 */
const useBundled = process.env.LEX_MOBILE_USE_BUNDLED === "1";
const serverUrl =
  process.env.LEX_MOBILE_SERVER_URL?.trim() ||
  (useBundled ? "" : "https://www.naintegracursos.com.br/lex/");

const config: CapacitorConfig = {
  appId: "br.com.naintegracursos.lex",
  appName: "NaIntegra Lex",
  webDir: "www",
  android: {
    allowMixedContent: false,
  },
  ios: {
    contentInset: "automatic",
    scheme: "NaIntegraLex",
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      launchAutoHide: true,
      backgroundColor: "#faf8f4",
      androidSplashResourceName: "splash",
      androidScaleType: "CENTER_CROP",
      showSpinner: false,
    },
    StatusBar: {
      style: "DARK",
      backgroundColor: "#faf8f4",
    },
  },
};

if (serverUrl) {
  config.server = {
    url: serverUrl.endsWith("/") ? serverUrl : `${serverUrl}/`,
    cleartext: false,
    androidScheme: "https",
  };
}

export default config;
