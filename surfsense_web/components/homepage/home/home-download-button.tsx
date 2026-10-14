import Link from "next/link";
import { DOWNLOADS_URL } from "@/components/site/site-content";
import { ArrowRightIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";

const TONES = {
	/** On the scene, where a dark pill would sink into the night sky. */
	light: {
		pill: "bg-card text-foreground hover:bg-secondary focus-visible:outline-white",
		dot: "bg-foreground text-background",
	},
	/** On the page's light ground, where a white pill would disappear. */
	dark: {
		pill: "bg-foreground text-background hover:bg-foreground/90 focus-visible:outline-ring",
		dot: "bg-background text-foreground",
	},
};

/** The download pill for sections set on the scene. */
export function HomeDownloadButton({ tone = "light" }: { tone?: keyof typeof TONES }) {
	return (
		<Link
			href={DOWNLOADS_URL}
			className={cn(
				"group inline-flex h-11 items-center gap-2.5 rounded-full pr-1.5 pl-5 text-sm font-semibold shadow-lg transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2",
				TONES[tone].pill
			)}
		>
			Download for desktop
			<span className={cn("grid size-8 place-items-center rounded-full", TONES[tone].dot)}>
				<ArrowRightIcon
					aria-hidden="true"
					className="size-4 transition-transform duration-150 group-hover:translate-x-0.5"
				/>
			</span>
		</Link>
	);
}
