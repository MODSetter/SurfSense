/**
 * Application-wide constants
 */

/**
 * Local storage key for the authentication bearer token
 * Used across auth-utils, hooks, and base-api.service
 */
export const AUTH_TOKEN_KEY = "surfsense_bearer_token";

/**
 * Default contact email address
 * Can be overridden via NEXT_PUBLIC_DEFAULT_CONTACT_EMAIL environment variable
 */
export const DEFAULT_CONTACT_EMAIL = process.env.NEXT_PUBLIC_DEFAULT_CONTACT_EMAIL || "support@example.com";

/**
 * Default copyright text with dynamic year
 */
export const DEFAULT_COPYRIGHT_TEXT = `SurfSense ${new Date().getFullYear()}`;
