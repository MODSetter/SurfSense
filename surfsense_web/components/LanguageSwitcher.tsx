"use client";

import { Globe } from "lucide-react";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useLocaleContext } from "@/contexts/LocaleContext";

/**
 * Language switcher component
 * Allows users to change the application language
 * Persists preference in localStorage
 */
export function LanguageSwitcher() {
	const { locale, setLocale } = useLocaleContext();

	// Supported languages configuration
	const languages = [
		{ code: "en" as const, name: "English", flag: "🇺🇸" },
		{ code: "zh" as const, name: "简体中文", flag: "🇨🇳" },
	];

	/**
	 * Handle language change
	 * Updates locale in context and localStorage
	 */
	const handleLanguageChange = (newLocale: string) => {
		setLocale(newLocale as "en" | "zh");
	};

	return (
		<Select value={locale} onValueChange={handleLanguageChange}>
			<SelectTrigger className="w-[110px] sm:w-[160px] h-8 sm:h-10 text-xs sm:text-sm px-2 sm:px-3 gap-1 sm:gap-2">
				<Globe className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
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
