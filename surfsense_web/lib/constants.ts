/**
 * Application-wide constants
 */

/**
 * Local storage key for the authentication bearer token
 * Used across auth-utils, hooks, and base-api.service
 */
export const AUTH_TOKEN_KEY = "surfsense_bearer_token";

/**
 * Default site configuration values
 * Used in SiteConfigContext and site-settings page
 * Can be overridden via environment variables
 */
export const DEFAULT_CONTACT_EMAIL = process.env.NEXT_PUBLIC_DEFAULT_CONTACT_EMAIL || "support@example.com";
export const DEFAULT_COPYRIGHT_TEXT = `SurfSense ${new Date().getFullYear()}`;
