import { Logo } from "@/components/Logo";

/** Fixed 4rem bar over a shared chat; the page pads its content by `pt-16`. */
export function PublicChatHeader() {
	return (
		<header className="fixed inset-x-0 top-0 z-60 flex h-16 items-center gap-2 border-b border-border/30 bg-main-panel/80 px-4 backdrop-blur-md">
			<Logo className="size-7" />
			<span className="text-sm font-semibold">SurfSense</span>
		</header>
	);
}
