import { loader } from "fumadocs-core/source";
import { createElement } from "react";
import { docs } from "@/.source/server";
import {
	BookOpen01Icon,
	BubbleChatIcon,
	ClipboardCheckIcon,
	Compass01Icon,
	ContainerIcon,
	CpuIcon,
	DownloadIcon,
	FavouriteIcon,
	FlaskConicalIcon,
	Radar01Icon,
	UnplugIcon,
	Wrench01Icon,
} from "@/components/ui/icons";

/**
 * The icons docs frontmatter and meta.json name, by those names. A whitelist,
 * so the docs bundle carries only these; add one here when a page names it.
 */
const DOCS_ICONS: Record<string, React.ComponentType> = {
	BookOpen: BookOpen01Icon,
	ClipboardCheck: ClipboardCheckIcon,
	Compass: Compass01Icon,
	Container: ContainerIcon,
	Cpu: CpuIcon,
	Download: DownloadIcon,
	FlaskConical: FlaskConicalIcon,
	Heart: FavouriteIcon,
	MessageCircle: BubbleChatIcon,
	Radar: Radar01Icon,
	Unplug: UnplugIcon,
	Wrench: Wrench01Icon,
};

export const source = loader({
	baseUrl: "/docs",
	source: docs.toFumadocsSource(),
	icon(icon) {
		if (icon && icon in DOCS_ICONS) return createElement(DOCS_ICONS[icon]);
	},
});
