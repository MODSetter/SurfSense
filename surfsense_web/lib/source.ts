import { loader } from "fumadocs-core/source";
import { docs } from "@/.source/server";
import { icons } from "lucide-react";
import { createElement } from "react";

export const source = loader({
	baseUrl: "/docs",
	source: docs.toFumadocsSource(),
	icon(icon) {
		if (icon && icon in icons)
			return createElement(icons[icon as keyof typeof icons]);
	},
});
