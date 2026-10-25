import {
	Agreement01Icon as Agreement01IconData,
	Alert02Icon as Alert02IconData,
	ArrowRightIcon as ArrowRightIconData,
	ArrowUp02Icon as ArrowUp02IconData,
	ArrowUpRight01Icon as ArrowUpRight01IconData,
	BookOpen01Icon as BookOpen01IconData,
	Briefcase01Icon as Briefcase01IconData,
	BubbleChatIcon as BubbleChatIconData,
	CableIcon as CableIconData,
	Calculator01Icon as Calculator01IconData,
	Calendar03Icon as Calendar03IconData,
	Cancel01Icon as Cancel01IconData,
	ChartHistogramIcon as ChartHistogramIconData,
	CheckIcon as CheckIconData,
	CheckmarkBadge02Icon as CheckmarkBadge02IconData,
	ChevronDownIcon as ChevronDownIconData,
	ChevronRightIcon as ChevronRightIconData,
	ClipboardCheckIcon as ClipboardCheckIconData,
	Compass01Icon as Compass01IconData,
	ComputerTerminal01Icon as ComputerTerminal01IconData,
	ContainerIcon as ContainerIconData,
	Copy01Icon as Copy01IconData,
	CpuIcon as CpuIconData,
	Database01Icon as Database01IconData,
	DotIcon as DotIconData,
	DownloadIcon as DownloadIconData,
	FavouriteIcon as FavouriteIconData,
	File02Icon as File02IconData,
	FlaskConicalIcon as FlaskConicalIconData,
	HistoryIcon as HistoryIconData,
	InformationCircleIcon as InformationCircleIconData,
	Key01Icon as Key01IconData,
	LaptopIcon as LaptopIconData,
	LinkSquare02Icon as LinkSquare02IconData,
	Mail01Icon as Mail01IconData,
	Megaphone01Icon as Megaphone01IconData,
	MenuTwoLineIcon as MenuTwoLineIconData,
	MinusSignIcon as MinusSignIconData,
	Notification03Icon as Notification03IconData,
	Pdf01Icon as Pdf01IconData,
	Plug01Icon as Plug01IconData,
	PlusIcon as PlusIconData,
	PodcastIcon as PodcastIconData,
	Presentation02Icon as Presentation02IconData,
	Radar01Icon as Radar01IconData,
	Search01Icon as Search01IconData,
	SecurityCheckIcon as SecurityCheckIconData,
	ServerStack01Icon as ServerStack01IconData,
	SourceCodeIcon as SourceCodeIconData,
	UnplugIcon as UnplugIconData,
	UserCircleIcon as UserCircleIconData,
	WifiOffIcon as WifiOffIconData,
	Wrench01Icon as Wrench01IconData,
	ZapIcon as ZapIconData,
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
export const Agreement01Icon = createIcon(Agreement01IconData);
export const Alert02Icon = createIcon(Alert02IconData);
export const ArrowRightIcon = createIcon(ArrowRightIconData);
export const ArrowUp02Icon = createIcon(ArrowUp02IconData);
export const ArrowUpRight01Icon = createIcon(ArrowUpRight01IconData);
export const BookOpen01Icon = createIcon(BookOpen01IconData);
export const Briefcase01Icon = createIcon(Briefcase01IconData);
export const BubbleChatIcon = createIcon(BubbleChatIconData);
export const CableIcon = createIcon(CableIconData);
export const Calculator01Icon = createIcon(Calculator01IconData);
export const Calendar03Icon = createIcon(Calendar03IconData);
export const Cancel01Icon = createIcon(Cancel01IconData);
export const ChartHistogramIcon = createIcon(ChartHistogramIconData);
export const CheckIcon = createIcon(CheckIconData);
export const CheckmarkBadgeIcon = createIcon(CheckmarkBadge02IconData);
export const ChevronDownIcon = createIcon(ChevronDownIconData);
export const ChevronRightIcon = createIcon(ChevronRightIconData);
export const ClipboardCheckIcon = createIcon(ClipboardCheckIconData);
export const Compass01Icon = createIcon(Compass01IconData);
export const ComputerTerminal01Icon = createIcon(ComputerTerminal01IconData);
export const ContainerIcon = createIcon(ContainerIconData);
export const Copy01Icon = createIcon(Copy01IconData);
export const CpuIcon = createIcon(CpuIconData);
export const Database01Icon = createIcon(Database01IconData);
export const DotIcon = createIcon(DotIconData);
export const DownloadIcon = createIcon(DownloadIconData);
export const FavouriteIcon = createIcon(FavouriteIconData);
export const File02Icon = createIcon(File02IconData);
export const FlaskConicalIcon = createIcon(FlaskConicalIconData);
export const HistoryIcon = createIcon(HistoryIconData);
export const InformationCircleIcon = createIcon(InformationCircleIconData);
export const Key01Icon = createIcon(Key01IconData);
export const LaptopIcon = createIcon(LaptopIconData);
export const LinkSquare02Icon = createIcon(LinkSquare02IconData);
export const Mail01Icon = createIcon(Mail01IconData);
export const Megaphone01Icon = createIcon(Megaphone01IconData);
export const MenuTwoLineIcon = createIcon(MenuTwoLineIconData);
export const MinusSignIcon = createIcon(MinusSignIconData);
export const Notification03Icon = createIcon(Notification03IconData);
export const Pdf01Icon = createIcon(Pdf01IconData);
export const Plug01Icon = createIcon(Plug01IconData);
export const PlusIcon = createIcon(PlusIconData);
export const PodcastIcon = createIcon(PodcastIconData);
export const Presentation02Icon = createIcon(Presentation02IconData);
export const Radar01Icon = createIcon(Radar01IconData);
export const Search01Icon = createIcon(Search01IconData);
export const SecurityCheckIcon = createIcon(SecurityCheckIconData);
export const ServerStack01Icon = createIcon(ServerStack01IconData);
export const SourceCodeIcon = createIcon(SourceCodeIconData);
export const UnplugIcon = createIcon(UnplugIconData);
export const UserCircleIcon = createIcon(UserCircleIconData);
export const WifiOffIcon = createIcon(WifiOffIconData);
export const Wrench01Icon = createIcon(Wrench01IconData);
export const ZapIcon = createIcon(ZapIconData);
