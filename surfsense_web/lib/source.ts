import { loader } from "fumadocs-core/source";
import {
	BookOpen,
	ClipboardCheck,
	Compass,
	Container,
	Download,
	FlaskConical,
	Heart,
	Unplug,
	Wrench,
	type LucideIcon,
} from "lucide-react";
import { createElement } from "react";
import { docs } from "@/.source/server";

// Explicit whitelist of icons used in docs MDX frontmatter.
// Avoids pulling the full lucide-react icon registry into the docs bundle:
// the barrel `icons` object prevents tree-shaking even with
// `optimizePackageImports` enabled, because the key is resolved dynamically.
const ICON_MAP: Record<string, LucideIcon> = {
	BookOpen,
	ClipboardCheck,
	Compass,
	Container,
	Download,
	FlaskConical,
	Heart,
	Unplug,
	Wrench,
};

export const source = loader({
	baseUrl: "/docs",
	source: docs.toFumadocsSource(),
	icon(icon) {
		if (icon && icon in ICON_MAP) return createElement(ICON_MAP[icon]);
	},
});
