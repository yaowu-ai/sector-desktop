/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DESKTOP_API_BASE_URL?: string
  readonly VITE_LICENSE_PUBLIC_KEY?: string
  readonly VITE_FEEDBACK_WS_PORT?: string
  readonly VITE_FEEDBACK_WS_PATH?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
