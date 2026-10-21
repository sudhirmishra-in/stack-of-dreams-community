/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_USE_MOCK_API?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface ImportMetaEnv {
  readonly VITE_AUTH_MODE?: string;
  readonly VITE_AUTH_AUTHORITY?: string;
  readonly VITE_AUTH_CLIENT_ID?: string;
  readonly VITE_AUTH_REDIRECT_URI?: string;
  readonly VITE_AUTH_SCOPE?: string;
  readonly VITE_AUTH_LOGOUT_DOMAIN?: string;
  /** "true" shows the Continue with Google button (the Cognito app client must also allow Google). */
  readonly VITE_AUTH_GOOGLE?: string;
}

interface ImportMetaEnv {
  readonly VITE_USE_MOCK_RESOURCES?: string;
  readonly VITE_RESOURCE_API_BASE_URL?: string;
}

interface ImportMetaEnv {
  readonly VITE_PILOT_API_BASE_URL?: string;
}
