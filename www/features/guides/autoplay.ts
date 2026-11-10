/**
 * A use-case video starts by itself when it scrolls into view, muted, because the videos
 * have no sound. Not for a visitor whose browser asks for less motion, nor for one saving
 * data: they press play.
 */
export function mayAutoplay({
	reducedMotion,
	saveData,
}: {
	reducedMotion: boolean;
	saveData: boolean;
}): boolean {
	return !reducedMotion && !saveData;
}

/** The browser's answers, read once the page is running. */
export function browserMayAutoplay(): boolean {
	const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
	return mayAutoplay({
		reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
		saveData: connection?.saveData === true,
	});
}
