/**
 * Centralized locale configuration
 * Single source of truth for all supported languages across the application
 * This file is shared between server and client code
 */

// Centralized language configuration with readonly type assertion
export const LANGUAGE_CONFIG = [
	{ code: "en", name: "English", flag: "🇺🇸" },
	{ code: "lv", name: "Latviešu", flag: "🇱🇻" },
	{ code: "sv", name: "Svenska", flag: "🇸🇪" },
] as const;

// Derive Locale type from LANGUAGE_CONFIG for single source of truth
// When you add/remove a language, the Locale type updates automatically
export type Locale = (typeof LANGUAGE_CONFIG)[number]["code"];

// Language configuration type for external use
export type LanguageConfig = (typeof LANGUAGE_CONFIG)[number];

// Supported locales array for validation (readonly for immutability)
export const SUPPORTED_LOCALES = LANGUAGE_CONFIG.map((lang) => lang.code) as const;

// Default locale
export const DEFAULT_LOCALE: Locale = "en";
