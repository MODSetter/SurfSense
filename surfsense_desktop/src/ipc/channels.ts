export const IPC_CHANNELS = {
  OPEN_EXTERNAL: 'open-external',
  GET_APP_VERSION: 'get-app-version',
  DEEP_LINK: 'deep-link',
  QUICK_ASK_TEXT: 'quick-ask-text',
  SET_QUICK_ASK_MODE: 'set-quick-ask-mode',
  GET_QUICK_ASK_MODE: 'get-quick-ask-mode',
  REPLACE_TEXT: 'replace-text',
  // Permissions
  GET_PERMISSIONS_STATUS: 'get-permissions-status',
  REQUEST_ACCESSIBILITY: 'request-accessibility',
  REQUEST_INPUT_MONITORING: 'request-input-monitoring',
  RESTART_APP: 'restart-app',
} as const;
