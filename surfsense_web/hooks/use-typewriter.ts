import { useEffect, useRef, useState } from "react";

/**
 * Animates text changes with a typewriter reveal effect, but only when
 * transitioning away from the `skipFor` placeholder (default "New Chat").
 * All other text values are shown instantly without animation.
 */
export function useTypewriter(text: string, speed = 35, skipFor = "New Chat"): string {
	const [displayed, setDisplayed] = useState(text);
	const prevTextRef = useRef(text);
	const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

	useEffect(() => {
		if (intervalRef.current) {
			clearInterval(intervalRef.current);
			intervalRef.current = null;
		}

		const prevText = prevTextRef.current;
		prevTextRef.current = text;

		const shouldAnimate = prevText === skipFor && text !== skipFor && !!text;

		if (!shouldAnimate) {
			setDisplayed(text);
			return;
		}

		let i = 0;
		intervalRef.current = setInterval(() => {
			i++;
			setDisplayed(text.slice(0, i));
			if (i >= text.length) {
				if (intervalRef.current) clearInterval(intervalRef.current);
				intervalRef.current = null;
			}
		}, speed);

		return () => {
			if (intervalRef.current) {
				clearInterval(intervalRef.current);
				intervalRef.current = null;
			}
		};
	}, [text, speed, skipFor]);

	return displayed;
}
