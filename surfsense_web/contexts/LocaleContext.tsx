"use client";

import type React from "react";
import { createContext, useContext, useEffect, useState } from "react";
import enMessages from "../messages/en.json";
import esMessages from "../messages/es.json";
import ptMessages from "../messages/pt.json";
import hiMessages from "../messages/hi.json";
import zhMessages from "../messages/zh.json";

type Locale = "en" | "es" | "pt" | "hi" | "zh";

const messagesMap: Record<Locale, typeof enMessages> = {
	en: enMessages,
	es: esMessages as typeof enMessages,
	pt: ptMessages as typeof enMessages,
	hi: hiMessages as typeof enMessages,
	zh: zhMessages as typeof enMessages,
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

	// Get messages based on current locale
	const messages = messagesMap[locale] || enMessages;

	// Load locale from localStorage after component mounts (client-side only)
	useEffect(() => {
		setMounted(true);
		if (typeof window !== "undefined") {
			const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
			if (stored && (["en", "es", "pt", "hi", "zh"] as const).includes(stored as Locale)) {
				setLocaleState(stored as Locale);
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
