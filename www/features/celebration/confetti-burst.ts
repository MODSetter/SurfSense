// The site palette: foreground, muted foreground, the notice blue and the sky.
const COLORS = ["#1e1e1e", "#626262", "#3f74c8", "#cfe3f7"];

/**
 * Two cannons, from the left and right edges, angled up and inward so they
 * cross over the window, for a moment that really happened: a paid license
 * saved, or a trial sent. Loaded on demand so no page carries it, and skipped
 * for anyone who asked the OS for less motion.
 */
export function fireConfetti(): void {
	if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
	void import("canvas-confetti")
		.then(({ default: confetti }) => {
			// Velocity is in pixels: 55 crosses a 375 px phone at once and leaves it,
			// so a narrow window gets slower, steeper cannons that stay on screen.
			const narrow = window.innerWidth < 640;
			const shared = {
				particleCount: narrow ? 45 : 60,
				spread: narrow ? 50 : 55,
				startVelocity: narrow ? 38 : 55,
				colors: COLORS,
				disableForReducedMotion: true,
			};
			// Mid-height, so the arcs pass over the headline and leave the result readable.
			const y = narrow ? 0.7 : 0.6;
			confetti({ ...shared, angle: narrow ? 70 : 60, origin: { x: 0, y } });
			confetti({ ...shared, angle: narrow ? 110 : 120, origin: { x: 1, y } });
		})
		.catch(() => {
			// A failed chunk load costs only the decoration.
		});
}
