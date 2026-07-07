import { atom } from "jotai";

// Atom to control the connector dialog open state from anywhere in the app
export const connectorDialogOpenAtom = atom(false);

/**
 * Requests the connector dialog to start an import flow for a specific
 * connector type (Google Drive / Composio Drive / OneDrive / Dropbox), set by
 * the Documents sidebar "Import" menu. `useConnectorDialog` consumes and clears
 * it.
 *
 * - `mode: "auto"` routes by connected-account count: none -> OAuth connect,
 *   one -> edit view, many -> accounts list. Used by "Connect" and "Manage".
 * - `mode: "connect"` always starts a fresh OAuth connect, even when an account
 *   already exists. Used by "Add another account".
 */
export interface ImportConnectorRequest {
	connectorType: string;
	mode: "auto" | "connect";
}

export const importConnectorRequestAtom = atom<ImportConnectorRequest | null>(null);
