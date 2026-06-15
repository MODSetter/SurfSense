/**
 * Environment configuration for the frontend.
 *
 * Docker deployments use same-origin relative browser URLs behind Caddy.
 * NEXT_PUBLIC_* values remain only as build-time fallbacks for packaged clients
 * like Electron, where there is no bundled Caddy origin.
 */

import packageJson from "../package.json";

// Build-time fallback for packaged clients. Docker runtime reads plain AUTH_TYPE
// through the runtime config provider instead.
export const AUTH_TYPE = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE || "GOOGLE";

// Backend API URL. An empty string is valid in proxy mode and means
// same-origin relative requests (e.g. /api/v1/... and /auth/...).
export const BACKEND_URL = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ?? "";

// Server-side backend URL. Relative browser URLs do not work from RSC/API route
// code, so server callers should use Docker DNS or an explicit public backend.
export const SERVER_BACKEND_URL =
	process.env.SURFSENSE_BACKEND_INTERNAL_URL ||
	// TODO: Remove FASTAPI_BACKEND_INTERNAL_URL after the post-Caddy env migration window.
	process.env.FASTAPI_BACKEND_INTERNAL_URL ||
	"http://backend:8000";

// Build-time fallback for packaged clients. Docker runtime reads plain ETL_SERVICE
// through the runtime config provider instead.
export const ETL_SERVICE = process.env.NEXT_PUBLIC_ETL_SERVICE || "DOCLING";

// Build-time fallback for packaged clients. Docker runtime reads plain
// DEPLOYMENT_MODE through the runtime config provider instead.
export const DEPLOYMENT_MODE = process.env.NEXT_PUBLIC_DEPLOYMENT_MODE || "self-hosted";

// App version - defaults to package.json version
// Can be overridden at build time with NEXT_PUBLIC_APP_VERSION for full git tag version
export const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION || packageJson.version;
