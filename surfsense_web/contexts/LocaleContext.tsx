"use client";

import type React from "react";
import { createContext, useContext, useEffect, useState } from "react";
import enMessages from "../messages/en.json";
import lvMessages from "../messages/lv.json";
import svMessages from "../messages/sv.json";
import {
	LANGUAGE_CONFIG,
	SUPPORTED_LOCALES,
	isValidLocale,
	type Locale,
	type LanguageConfig,
} from "@/lib/locale-config";

// Re-export types and config for backward compatibility
export type { Locale, LanguageConfig };
export { LANGUAGE_CONFIG, SUPPORTED_LOCALES, isValidLocale };

// Message map for type-safe locale selection
const messageMap: Record<Locale, typeof enMessages> = {
	en: enMessages,
	lv: lvMessages,
	sv: svMessages,
};

interface LocaleContextType {
	locale: Locale;
	messages: typeof enMessages;
	setLocale: (locale: Locale) => void;
}

const LocaleContext = createContext<LocaleContextType | undefined>(undefined);

const LOCALE_STORAGE_KEY = "surfsense-locale";

export function LocaleProvider({ children }: { children: React.ReactNode }) {
	// Always start with 'en' to avoid hydration mismatch
	// Then sync with localStorage after mount
	const [locale, setLocaleState] = useState<Locale>("en");
	const [mounted, setMounted] = useState(false);

	// Get messages based on current locale using map
	const messages = messageMap[locale];

	// Load locale from localStorage after component mounts (client-side only)
	useEffect(() => {
		setMounted(true);
		if (typeof window !== "undefined") {
			const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
			if (isValidLocale(stored)) {
				setLocaleState(stored);
			}
		}
	}, []);

	// Update locale and persist to localStorage
	const setLocale = (newLocale: Locale) => {
		setLocaleState(newLocale);
		if (typeof window !== "undefined") {
			localStorage.setItem(LOCALE_STORAGE_KEY, newLocale);
			// Update HTML lang attribute
			document.documentElement.lang = newLocale;
		}
	};

	// Set HTML lang attribute when locale changes
	useEffect(() => {
		if (typeof window !== "undefined" && mounted) {
			document.documentElement.lang = locale;
		}
	}, [locale, mounted]);

	return (
		<LocaleContext.Provider value={{ locale, messages, setLocale }}>
			{children}
		</LocaleContext.Provider>
	);
}

export function useLocaleContext() {
	const context = useContext(LocaleContext);
	if (context === undefined) {
		throw new Error("useLocaleContext must be used within a LocaleProvider");
	}
	return context;
}
