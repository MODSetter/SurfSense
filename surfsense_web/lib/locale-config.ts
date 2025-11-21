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

// Supported locales array for validation (readonly with runtime immutability)
// Using Object.freeze() for runtime protection in addition to TypeScript's 'as const'
// TypeScript automatically infers the correct readonly tuple type
export const SUPPORTED_LOCALES = Object.freeze(
	LANGUAGE_CONFIG.map((lang) => lang.code)
);

// Default locale
export const DEFAULT_LOCALE: Locale = "en";

/**
 * Type guard to validate if a value is a supported locale
 * Centralized validation logic used across the application
 *
 * @param value - The value to check
 * @returns true if the value is a valid Locale, false otherwise
 */
export function isValidLocale(value: unknown): value is Locale {
	return typeof value === "string" && SUPPORTED_LOCALES.some((locale) => locale === value);
}
