/**
 * Environment configuration for the frontend.
 *
 * This file centralizes access to NEXT_PUBLIC_* environment variables.
 * For Docker deployments, these placeholders are replaced at container startup
 * via sed in the entrypoint script.
 *
 * IMPORTANT: Do not use template literals or complex expressions with these values
 * as it may prevent the sed replacement from working correctly.
 */

// Auth type: "LOCAL" for email/password, "GOOGLE" for OAuth
// Placeholder: __NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE__
export const AUTH_TYPE = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE || "GOOGLE";

// Backend API URL
// Placeholder: __NEXT_PUBLIC_FASTAPI_BACKEND_URL__
export const BACKEND_URL = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

// ETL Service: "DOCLING" or "UNSTRUCTURED"
// Placeholder: __NEXT_PUBLIC_ETL_SERVICE__
export const ETL_SERVICE = process.env.NEXT_PUBLIC_ETL_SERVICE || "DOCLING";

// Deployment Mode: "self-hosted" or "cloud"
// Matches backend's SURFSENSE_DEPLOYMENT_MODE - defaults to "self-hosted"
// self-hosted: Full access to local file system connectors (Obsidian, etc.)
// cloud: Only cloud-based connectors available
// Placeholder: __NEXT_PUBLIC_DEPLOYMENT_MODE__
export const DEPLOYMENT_MODE = process.env.NEXT_PUBLIC_DEPLOYMENT_MODE || "self-hosted";

// Helper to check if local auth is enabled
export const isLocalAuth = () => AUTH_TYPE === "LOCAL";

// Helper to check if Google auth is enabled
export const isGoogleAuth = () => AUTH_TYPE === "GOOGLE";

// Helper to check if running in self-hosted mode
export const isSelfHosted = () => DEPLOYMENT_MODE === "self-hosted";

// Helper to check if running in cloud mode
export const isCloud = () => DEPLOYMENT_MODE === "cloud";
