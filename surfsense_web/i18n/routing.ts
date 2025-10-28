import { createNavigation } from "next-intl/navigation";
import { defineRouting } from "next-intl/routing";

/**
 * Internationalization routing configuration
 * Defines supported locales and routing behavior for the application
 */
export const routing = defineRouting({
	// A list of all locales that are supported
	locales: ["en", "zh"],

	// Used when no locale matches
	defaultLocale: "en",

	// The `localePrefix` setting controls whether the locale is included in the pathname
	// 'as-needed': Only add locale prefix when not using the default locale
	localePrefix: "as-needed",
});

// Lightweight wrappers around Next.js' navigation APIs
// that will consider the routing configuration
export const { Link, redirect, usePathname, useRouter, getPathname } = createNavigation(routing);
