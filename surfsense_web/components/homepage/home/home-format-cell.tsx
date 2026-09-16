import {
	AudioLines,
	FileCode,
	FileSpreadsheet,
	FileText,
	ImageIcon,
	ListChecks,
	type LucideIcon,
	Network,
	PlayingCardsFan,
	PlusIcon,
	Presentation,
} from "lucide-react";
import { FORMATS, type Format } from "@/components/homepage/home/home-content";
import { CardSpotlight } from "@/components/ui/card-spotlight";
import { cn } from "@/lib/utils";

/**
 * Icon per format key, copied from the in-app Studio library's own catalog
 * (`features/artifacts/lib/artifact-format-catalog.ts`) rather than picked
 * fresh — the app already decided flashcards are a card fan and a mind map is
 * a network, and this row should draw the same formats the same way.
 */
const FORMAT_ICONS: Record<string, LucideIcon> = {
	summary: FileText,
	docx: FileText,
	pptx: Presentation,
	xlsx: FileSpreadsheet,
	html: FileCode,
	pdf: FileText,
	mindmap: Network,
	flashcards: PlayingCardsFan,
	quiz: ListChecks,
	podcast: AudioLines,
	image: ImageIcon,
	infographic: ImageIcon,
};

/** Dot-reveal colours per format, as `[r, g, b]` pairs the reveal blends
 *  between: a different hue for each of the twelve so no two cells light up
 *  the same. Values are Tailwind's 500-weight palette, which reads on the
 *  dark ground. */
const FORMAT_COLORS: Record<string, number[][]> = {
	summary: [
		[245, 158, 11],
		[249, 115, 22],
	],
	docx: [
		[59, 130, 246],
		[14, 165, 233],
	],
	pptx: [
		[249, 115, 22],
		[239, 68, 68],
	],
	xlsx: [
		[34, 197, 94],
		[16, 185, 129],
	],
	html: [
		[139, 92, 246],
		[168, 85, 247],
	],
	pdf: [
		[239, 68, 68],
		[244, 63, 94],
	],
	mindmap: [
		[6, 182, 212],
		[20, 184, 166],
	],
	flashcards: [
		[236, 72, 153],
		[217, 70, 239],
	],
	quiz: [
		[132, 204, 22],
		[34, 197, 94],
	],
	podcast: [
		[242, 106, 75],
		[251, 146, 60],
	],
	image: [
		[99, 102, 241],
		[139, 92, 246],
	],
	infographic: [
		[234, 179, 8],
		[245, 158, 11],
	],
};

/** Where a cell lands in a grid of `columns`, and what that means for its
 *  chrome: checkerboard tint, and whether it has a neighbour to its right and
 *  below (which decides its hairlines and whether its corner is an interior one). */
function placement(index: number, columns: number) {
	const rows = Math.ceil(FORMATS.length / columns);
	const col = index % columns;
	const row = Math.floor(index / columns);
	return {
		tinted: (row + col) % 2 === 0,
		lastCol: col === columns - 1,
		lastRow: row === rows - 1,
	};
}

/**
 * A format cell in the same grid vocabulary as the "Trusted by experts at"
 * logo cloud (`home-logos.tsx`): per-cell hairlines, a `secondary`
 * checkerboard, and a plus mark where four cells meet. The logo cloud
 * hardcodes those per cell for its fixed eight; with twelve cells that reflow
 * from two columns to four at `md`, they are worked out from the index here
 * for both layouts.
 *
 * The chrome sits on an outer wrapper and the `CardSpotlight` (components/ui)
 * inside it, because the card is `overflow: hidden` for its spotlight layer
 * and would clip a plus mark hung off its corner. `.ss-home-cell` /
 * `.ss-home-format-cell` are unlayered and outrank the card's own Tailwind
 * defaults (`p-10`, `border-neutral-800`): the card keeps the row's gutter
 * padding and draws no border of its own. It is `h-full` because the grid
 * stretches every wrapper in a row to the tallest one, and a card sized only
 * to its own text would leave a band at the bottom the spotlight never
 * reaches. The content sits at `z-20`, above the card's `z-0` spotlight
 * layer, as the card's demo does.
 */
export function HomeFormatCell({ format, index }: { format: Format; index: number }) {
	const Icon = FORMAT_ICONS[format.key] ?? FileText;
	const base = placement(index, 2);
	const md = placement(index, 4);

	const plusBase = !base.lastCol && !base.lastRow;
	const plusMd = !md.lastCol && !md.lastRow;
	const plusVisibility =
		plusBase && plusMd ? "" : plusBase ? "md:hidden" : plusMd ? "hidden md:block" : null;

	return (
		<div
			className={cn(
				"relative border-[color:var(--border)]",
				base.tinted ? "bg-secondary" : "bg-background",
				md.tinted ? "md:bg-secondary" : "md:bg-background",
				!base.lastCol && "border-r",
				md.lastCol ? "md:border-r-0" : "md:border-r",
				!base.lastRow && "border-b",
				md.lastRow ? "md:border-b-0" : "md:border-b"
			)}
		>
			<CardSpotlight
				className="ss-home-cell ss-home-format-cell h-full rounded-none bg-transparent"
				dotColors={FORMAT_COLORS[format.key]}
			>
				<div className="relative z-20">
					<Icon aria-hidden="true" className="ss-home-format-icon" />
					<p className="ss-home-h3 mt-4">{format.label}</p>
					<p className="ss-home-body mt-1.5 max-w-sm text-sm">{format.body}</p>
				</div>
			</CardSpotlight>

			{plusVisibility !== null && (
				<PlusIcon
					aria-hidden="true"
					className={cn(
						"ss-home-logo-plus absolute z-10 size-6 -right-[12.5px] -bottom-[12.5px]",
						plusVisibility
					)}
					strokeWidth={1}
				/>
			)}
		</div>
	);
}
