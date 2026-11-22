/**
 * One vertical rhythm for the homepage's ruled sections: the same space above
 * every heading and below every section's content, so the gap between any two
 * sections is equal and the dividing rule sits halfway through it. The footer's
 * call to action starts on `head` too, so the last gap matches the others.
 */
export const sectionSpacing = {
	head: "pt-16 md:pt-32",
	foot: "pb-16 md:pb-32",
} as const;
