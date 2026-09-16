import {
	AiSearchLinesIcon as AiSearchLinesIconData,
	ArrowRightIcon as ArrowRightIconData,
	ArrowUp02Icon as ArrowUp02IconData,
	ArrowUpRight01Icon as ArrowUpRight01IconData,
	Cards01Icon as Cards01IconData,
	ChartHistogramIcon as ChartHistogramIconData,
	CheckIcon as CheckIconData,
	ChevronDownIcon as ChevronDownIconData,
	ChevronRightIcon as ChevronRightIconData,
	ComputerTerminal01Icon as ComputerTerminal01IconData,
	Database01Icon as Database01IconData,
	DownloadIcon as DownloadIconData,
	File02Icon as File02IconData,
	Image01Icon as Image01IconData,
	Key01Icon as Key01IconData,
	LinkSquare02Icon as LinkSquare02IconData,
	Megaphone01Icon as Megaphone01IconData,
	NetworkIcon as NetworkIconData,
	Notification03Icon as Notification03IconData,
	Pdf01Icon as Pdf01IconData,
	Plug01Icon as Plug01IconData,
	PlusIcon as PlusIconData,
	PodcastIcon as PodcastIconData,
	Presentation02Icon as Presentation02IconData,
	Quiz02Icon as Quiz02IconData,
	SecurityCheckIcon as SecurityCheckIconData,
	ServerStack01Icon as ServerStack01IconData,
	SourceCodeIcon as SourceCodeIconData,
	ViewIcon as ViewIconData,
	ViewOffSlashIcon as ViewOffSlashIconData,
	WebDesign01Icon as WebDesign01IconData,
	Wrench01Icon as Wrench01IconData,
	Xls01Icon as Xls01IconData,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import * as React from "react";

/**
 * Hugeicons for the public site, wrapped as plain components.
 *
 * A port of `surfsense_local/frontend/src/components/ui/icons.tsx`, so the
 * marketing pages draw the same icon set as the app. Each export is a
 * component that takes `className`, `strokeWidth`, `aria-*` and so on
 * directly — the shape lucide's components have — rather than the
 * `<HugeiconsIcon icon={...} />` form, so call sites and icon maps read the
 * same as before and only the import changes.
 *
 * Only the icons the public pages actually use are wrapped; add to the list
 * as pages need them, keeping the export named after the hugeicons data it
 * wraps so it can be found in that package's catalog.
 */

type IconData = React.ComponentProps<typeof HugeiconsIcon>["icon"];
type IconProps = Omit<React.ComponentProps<typeof HugeiconsIcon>, "icon" | "strokeWidth"> & {
	strokeWidth?: React.SVGProps<SVGSVGElement>["strokeWidth"];
};

export type Icon = React.ForwardRefExoticComponent<IconProps & React.RefAttributes<SVGSVGElement>>;

function createIcon(icon: IconData): Icon {
	return React.forwardRef<SVGSVGElement, IconProps>(function Icon(
		{ strokeWidth = 2, ...props },
		ref
	) {
		const width =
			typeof strokeWidth === "number" ? strokeWidth : Number.parseFloat(strokeWidth) || 2;
		return <HugeiconsIcon ref={ref} icon={icon} strokeWidth={width} {...props} />;
	});
}

export const AiSearchLinesIcon = createIcon(AiSearchLinesIconData);
export const ArrowRightIcon = createIcon(ArrowRightIconData);
export const ArrowUp02Icon = createIcon(ArrowUp02IconData);
export const ArrowUpRight01Icon = createIcon(ArrowUpRight01IconData);
export const Cards01Icon = createIcon(Cards01IconData);
export const ChartHistogramIcon = createIcon(ChartHistogramIconData);
export const CheckIcon = createIcon(CheckIconData);
export const ChevronDownIcon = createIcon(ChevronDownIconData);
export const ChevronRightIcon = createIcon(ChevronRightIconData);
export const ComputerTerminal01Icon = createIcon(ComputerTerminal01IconData);
export const Database01Icon = createIcon(Database01IconData);
export const DownloadIcon = createIcon(DownloadIconData);
export const File02Icon = createIcon(File02IconData);
export const Image01Icon = createIcon(Image01IconData);
export const Key01Icon = createIcon(Key01IconData);
export const LinkSquare02Icon = createIcon(LinkSquare02IconData);
export const Megaphone01Icon = createIcon(Megaphone01IconData);
export const NetworkIcon = createIcon(NetworkIconData);
export const Notification03Icon = createIcon(Notification03IconData);
export const Pdf01Icon = createIcon(Pdf01IconData);
export const Plug01Icon = createIcon(Plug01IconData);
export const PlusIcon = createIcon(PlusIconData);
export const PodcastIcon = createIcon(PodcastIconData);
export const Presentation02Icon = createIcon(Presentation02IconData);
export const Quiz02Icon = createIcon(Quiz02IconData);
export const SecurityCheckIcon = createIcon(SecurityCheckIconData);
export const ServerStack01Icon = createIcon(ServerStack01IconData);
export const SourceCodeIcon = createIcon(SourceCodeIconData);
export const ViewIcon = createIcon(ViewIconData);
export const ViewOffSlashIcon = createIcon(ViewOffSlashIconData);
export const WebDesign01Icon = createIcon(WebDesign01IconData);
export const Wrench01Icon = createIcon(Wrench01IconData);
export const Xls01Icon = createIcon(Xls01IconData);
