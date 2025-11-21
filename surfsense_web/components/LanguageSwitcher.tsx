"use client";

import { Globe } from "lucide-react";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useLocaleContext, type Locale } from "@/contexts/LocaleContext";

/**
 * Language switcher component
 * Allows users to change the application language
 * Persists preference in localStorage
 */
export function LanguageSwitcher() {
	const { locale, setLocale } = useLocaleContext();

	// Supported languages configuration
	const languages: Array<{ code: Locale; name: string; flag: string }> = [
		{ code: "en", name: "English", flag: "🇺🇸" },
		{ code: "lv", name: "Latviešu", flag: "🇱🇻" },
		{ code: "sv", name: "Svenska", flag: "🇸🇪" },
	];

	/**
	 * Handle language change
	 * Updates locale in context and localStorage
	 */
	const handleLanguageChange = (newLocale: string) => {
		setLocale(newLocale as Locale);
	};

	return (
		<Select value={locale} onValueChange={handleLanguageChange}>
			<SelectTrigger className="w-[160px]">
				<Globe className="mr-2 h-4 w-4" />
				<SelectValue>
					{languages.find((lang) => lang.code === locale)?.name || "English"}
				</SelectValue>
			</SelectTrigger>
			<SelectContent>
				{languages.map((language) => (
					<SelectItem key={language.code} value={language.code}>
						<span className="flex items-center gap-2">
							<span>{language.flag}</span>
							<span>{language.name}</span>
						</span>
					</SelectItem>
				))}
			</SelectContent>
		</Select>
	);
}
