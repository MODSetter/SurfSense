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
  // Autocomplete
  AUTOCOMPLETE_CONTEXT: 'autocomplete-context',
  ACCEPT_SUGGESTION: 'accept-suggestion',
  DISMISS_SUGGESTION: 'dismiss-suggestion',
  UPDATE_SUGGESTION_TEXT: 'update-suggestion-text',
  SET_AUTOCOMPLETE_ENABLED: 'set-autocomplete-enabled',
  GET_AUTOCOMPLETE_ENABLED: 'get-autocomplete-enabled',
} as const;
