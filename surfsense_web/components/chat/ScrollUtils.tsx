import { type RefObject, useEffect } from "react";

/**
 * Function to scroll to the bottom of a container
 */
export const scrollToBottom = (ref: RefObject<HTMLDivElement>) => {
	ref.current?.scrollIntoView({ behavior: "smooth" });
};

/**
 * Hook to scroll to bottom when messages change
 */
export const useScrollToBottom = (ref: RefObject<HTMLDivElement>, dependencies: any[]) => {
	useEffect(() => {
		scrollToBottom(ref);
	}, dependencies);
};

/**
 * Function to check scroll position and update indicators
 */
export const updateScrollIndicators = (
	tabsListRef: RefObject<HTMLDivElement>,
	setCanScrollLeft: (value: boolean) => void,
	setCanScrollRight: (value: boolean) => void
) => {
	if (tabsListRef.current) {
		const { scrollLeft, scrollWidth, clientWidth } = tabsListRef.current;
		setCanScrollLeft(scrollLeft > 0);
		setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 10); // 10px buffer
	}
};

/**
 * Hook to initialize scroll indicators and add resize listener
 */
export const useScrollIndicators = (
	tabsListRef: RefObject<HTMLDivElement>,
	setCanScrollLeft: (value: boolean) => void,
	setCanScrollRight: (value: boolean) => void
) => {
	const updateIndicators = () =>
		updateScrollIndicators(tabsListRef, setCanScrollLeft, setCanScrollRight);

	useEffect(() => {
		updateIndicators();
		// Add resize listener to update indicators when window size changes
		window.addEventListener("resize", updateIndicators);
		return () => window.removeEventListener("resize", updateIndicators);
	}, [updateIndicators]);

	return updateIndicators;
};

/**
 * Function to scroll tabs list left
 */
export const scrollTabsLeft = (
	tabsListRef: RefObject<HTMLDivElement>,
	updateIndicators: () => void
) => {
	if (tabsListRef.current) {
		tabsListRef.current.scrollBy({ left: -200, behavior: "smooth" });
		// Update indicators after scrolling
		setTimeout(updateIndicators, 300);
	}
};

/**
 * Function to scroll tabs list right
 */
export const scrollTabsRight = (
	tabsListRef: RefObject<HTMLDivElement>,
	updateIndicators: () => void
) => {
	if (tabsListRef.current) {
		tabsListRef.current.scrollBy({ left: 200, behavior: "smooth" });
		// Update indicators after scrolling
		setTimeout(updateIndicators, 300);
	}
};
