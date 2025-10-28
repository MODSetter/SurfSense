import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

/**
 * Configuration for internationalization request handling
 * This function is called for each request to determine the locale and load translations
 */
export default getRequestConfig(async ({ requestLocale }) => {
	// This typically corresponds to the `[locale]` segment
	let locale = await requestLocale;

	// Ensure that the incoming `locale` is valid
	if (!locale || !routing.locales.includes(locale as any)) {
		locale = routing.defaultLocale;
	}

	return {
		locale,
		messages: (await import(`../messages/${locale}.json`)).default,
	};
});
