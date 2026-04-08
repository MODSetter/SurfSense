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
  REQUEST_SCREEN_RECORDING: 'request-screen-recording',
  RESTART_APP: 'restart-app',
  // Autocomplete
  AUTOCOMPLETE_CONTEXT: 'autocomplete-context',
  ACCEPT_SUGGESTION: 'accept-suggestion',
  DISMISS_SUGGESTION: 'dismiss-suggestion',
  SET_AUTOCOMPLETE_ENABLED: 'set-autocomplete-enabled',
  GET_AUTOCOMPLETE_ENABLED: 'get-autocomplete-enabled',
  // Folder sync channels
  FOLDER_SYNC_SELECT_FOLDER: 'folder-sync:select-folder',
  FOLDER_SYNC_ADD_FOLDER: 'folder-sync:add-folder',
  FOLDER_SYNC_REMOVE_FOLDER: 'folder-sync:remove-folder',
  FOLDER_SYNC_GET_FOLDERS: 'folder-sync:get-folders',
  FOLDER_SYNC_GET_STATUS: 'folder-sync:get-status',
  FOLDER_SYNC_FILE_CHANGED: 'folder-sync:file-changed',
  FOLDER_SYNC_WATCHER_READY: 'folder-sync:watcher-ready',
  FOLDER_SYNC_PAUSE: 'folder-sync:pause',
  FOLDER_SYNC_RESUME: 'folder-sync:resume',
  FOLDER_SYNC_RENDERER_READY: 'folder-sync:renderer-ready',
  FOLDER_SYNC_GET_PENDING_EVENTS: 'folder-sync:get-pending-events',
  FOLDER_SYNC_ACK_EVENTS: 'folder-sync:ack-events',
  BROWSE_FILES: 'browse:files',
  READ_LOCAL_FILES: 'browse:read-local-files',
  // Auth token sync across windows
  GET_AUTH_TOKENS: 'auth:get-tokens',
  SET_AUTH_TOKENS: 'auth:set-tokens',
  // Keyboard shortcut configuration
  GET_SHORTCUTS: 'shortcuts:get',
  SET_SHORTCUTS: 'shortcuts:set',
  // Active search space
  GET_ACTIVE_SEARCH_SPACE: 'search-space:get-active',
  SET_ACTIVE_SEARCH_SPACE: 'search-space:set-active',
} as const;
