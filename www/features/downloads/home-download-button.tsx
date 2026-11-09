import Link from "next/link";
import { HomeButton } from "@/components/site/home-button";
import { DOWNLOADS_URL } from "@/components/site/site-content";
import { cn } from "@/components/ui/cn";

const TONES = {
	/** On the scene, where a dark button would sink into the night sky. */
	light: "bg-card text-foreground hover:bg-secondary",
	/** On the page's light ground, where a white button would disappear. */
	dark: "",
};

/** The download call to action. */
export function HomeDownloadButton({ tone = "light" }: { tone?: keyof typeof TONES }) {
	return (
		<HomeButton
			asChild
			size="xl"
			className={cn("h-11 rounded-full px-5 text-[0.9375rem]", TONES[tone])}
		>
			<Link href={DOWNLOADS_URL}>Download for desktop</Link>
		</HomeButton>
	);
}
