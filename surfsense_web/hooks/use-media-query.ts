import { useEffect, useState } from "react";

/**
 * Custom hook that tracks if a media query matches
 * @param query - The media query string to match (e.g., "(min-width: 768px)")
 * @returns boolean - True if the media query matches, false otherwise
 */
export function useMediaQuery(query: string): boolean {
	const [matches, setMatches] = useState(false);

	useEffect(() => {
		// Check if we're in the browser (handle SSR)
		if (typeof window === "undefined") {
			return;
		}

		const mediaQuery = window.matchMedia(query);

		// Set initial value
		setMatches(mediaQuery.matches);

		// Create event listener
		const handler = (event: MediaQueryListEvent) => {
			setMatches(event.matches);
		};

		// Add event listener
		mediaQuery.addEventListener("change", handler);

		// Cleanup
		return () => {
			mediaQuery.removeEventListener("change", handler);
		};
	}, [query]);

	return matches;
}
