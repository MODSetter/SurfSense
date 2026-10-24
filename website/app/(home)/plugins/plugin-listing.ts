import type * as React from "react";

/**
 * One plugin as the site shows it, read from an entry of either list: SurfSense's own
 * (`first-party-plugins.json`) or the registry's. Both share the app's entry shape.
 */

export const REGISTRY_ORIGIN = "https://plugins.surfsense.com";

// The registry's id rule; anything else would make a bad page address.
const PLUGIN_ID = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const ICON_NAME = /^[a-z0-9][a-z0-9_-]*\.(svg|png)$/;

export type PluginSignIn = "license" | "token" | "oauth" | "none";

export type PluginListing = {
	id: string;
	name: string;
	description: string;
	author: string;
	/** The plugin's page on this site. */
	href: string;
	logo:
		| { kind: "inline"; Logo: (props: React.SVGProps<SVGSVGElement>) => React.ReactElement }
		| { kind: "image"; src: string }
		| { kind: "letter"; letter: string };
	publisher: "surfsense" | "third-party";
	access: "license" | "free" | "external";
	/** What a paid plugin's user must buy, in the publisher's words. */
	accessNote: string | null;
	verification?: "verified" | "community";
	signIn: PluginSignIn;
	/** The host every call goes to; the others see only an OAuth sign-in. */
	serverHost: string;
	signInHosts: string[];
	tools: string[];
	about: string | null;
	/** The month it was listed, as `2026-10`. */
	added: string | null;
	homepage: string | null;
	privacyPolicy: string | null;
};

type Entry = Record<string, unknown>;

function text(value: unknown): string | null {
	return typeof value === "string" && value.trim() ? value : null;
}

function https(value: unknown): string | null {
	return typeof value === "string" && value.startsWith("https://") ? value : null;
}

function hostOf(url: unknown): string | null {
	if (typeof url !== "string") return null;
	try {
		return new URL(url).host.toLowerCase();
	} catch {
		return null;
	}
}

// A key in `Authorization` or in headers of the publisher's own is the same ask: a key.
function signInOf(auth: unknown): PluginSignIn {
	const type = auth && typeof auth === "object" ? (auth as Entry).type : null;
	if (type === "license" || type === "oauth" || type === "none") return type;
	return "token";
}

/** Null when the entry lacks what its card needs, so one bad entry never breaks the page. */
export function listingFromEntry(
	raw: unknown,
	publisher: PluginListing["publisher"]
): PluginListing | null {
	if (!raw || typeof raw !== "object") return null;
	const entry = raw as Entry;
	const id = text(entry.id);
	const name = text(entry.name);
	const description = text(entry.description);
	const author = text(entry.author);
	const serverHost = hostOf(entry.url);
	if (!id || !PLUGIN_ID.test(id) || !name || !description || !author || !serverHost) return null;

	const hosts = Array.isArray(entry.hosts) ? entry.hosts.filter((h) => typeof h === "string") : [];
	const icon = typeof entry.icon === "string" && ICON_NAME.test(entry.icon) ? entry.icon : null;
	const access =
		entry.access === "license" ? "license" : entry.access === "external" ? "external" : "free";
	return {
		id,
		name,
		description,
		author,
		href: `/plugins/${id}`,
		// SurfSense's own get their inline marks in `plugin-list.ts`.
		logo:
			publisher === "third-party" && icon
				? { kind: "image", src: `${REGISTRY_ORIGIN}/icons/${icon}` }
				: { kind: "letter", letter: name.trim().charAt(0) },
		publisher,
		access,
		accessNote: access === "external" ? text(entry.access_note) : null,
		verification:
			publisher === "surfsense"
				? undefined
				: entry.verification === "verified"
					? "verified"
					: "community",
		signIn: signInOf(entry.auth),
		serverHost,
		signInHosts: hosts.filter((host) => host !== serverHost),
		tools: Array.isArray(entry.tools) ? entry.tools.filter((t) => typeof t === "string") : [],
		about: text(entry.about),
		added:
			typeof entry.added === "string" && /^\d{4}-\d{2}$/.test(entry.added) ? entry.added : null,
		homepage: https(entry.homepage),
		privacyPolicy: https(entry.privacy_policy),
	};
}
