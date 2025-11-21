"use client";

import { Globe } from "lucide-react";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	useLocaleContext,
	LANGUAGE_CONFIG,
	isValidLocale,
	type Locale,
} from "@/contexts/LocaleContext";

/**
 * Language switcher component
 * Allows users to change the application language
 * Persists preference in localStorage
 */
export function LanguageSwitcher() {
	const { locale, setLocale } = useLocaleContext();

	/**
	 * Handle language change
	 * Updates locale in context and localStorage
	 * Validates the locale before setting it
	 */
	const handleLanguageChange = (newLocale: string) => {
		if (isValidLocale(newLocale)) {
			setLocale(newLocale);
		}
	};

	return (
		<Select value={locale} onValueChange={handleLanguageChange}>
			<SelectTrigger className="w-[160px]">
				<Globe className="mr-2 h-4 w-4" />
				<SelectValue>
					{LANGUAGE_CONFIG.find((lang) => lang.code === locale)?.name || "English"}
				</SelectValue>
			</SelectTrigger>
			<SelectContent>
				{LANGUAGE_CONFIG.map((language) => (
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
