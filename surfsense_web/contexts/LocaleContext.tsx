"use client";

import type React from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import enMessages from "../messages/en.json";

type Locale = "en" | "es" | "pt" | "hi" | "zh";

/**
 * Dynamically load locale messages on demand.
 * English is the default and always available synchronously.
 */
const loadMessages = async (locale: Locale): Promise<typeof enMessages> => {
	switch (locale) {
		case "es":
			return (await import("../messages/es.json")).default;
		case "hi":
			return (await import("../messages/hi.json")).default;
		case "pt":
			return (await import("../messages/pt.json")).default;
		case "zh":
			return (await import("../messages/zh.json")).default;
		default:
			return enMessages;
	}
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
	const [messages, setMessages] = useState<typeof enMessages>(enMessages);
	const [mounted, setMounted] = useState(false);

	// Load locale from localStorage after component mounts (client-side only)
	useEffect(() => {
		setMounted(true);
		if (typeof window !== "undefined") {
			const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
			if (stored && (["en", "es", "pt", "hi", "zh"] as const).includes(stored as Locale)) {
				const storedLocale = stored as Locale;
				setLocaleState(storedLocale);
				// Load messages for non-English locale
				if (storedLocale !== "en") {
					loadMessages(storedLocale).then(setMessages);
				}
			}
		}
	}, []);

	// Update locale and persist to localStorage
	const setLocale = useCallback(async (newLocale: Locale) => {
		// Load messages for the new locale
		const newMessages = await loadMessages(newLocale);
		setMessages(newMessages);
		setLocaleState(newLocale);
		if (typeof window !== "undefined") {
			localStorage.setItem(LOCALE_STORAGE_KEY, newLocale);
			// Update HTML lang attribute
			document.documentElement.lang = newLocale;
		}
	}, []);

	// Set HTML lang attribute when locale changes
	useEffect(() => {
		if (typeof window !== "undefined" && mounted) {
			document.documentElement.lang = locale;
		}
	}, [locale, mounted]);

	const contextValue = useMemo(
		() => ({ locale, messages, setLocale }),
		[locale, messages, setLocale]
	);

	return <LocaleContext.Provider value={contextValue}>{children}</LocaleContext.Provider>;
}

export function useLocaleContext() {
	const context = useContext(LocaleContext);
	if (context === undefined) {
		throw new Error("useLocaleContext must be used within a LocaleProvider");
	}
	return context;
}
