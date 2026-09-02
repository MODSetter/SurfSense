export function shuffledCardOrder(cardCount: number, random = Math.random): number[] {
	const order = Array.from({ length: cardCount }, (_, index) => index);
	for (let index = order.length - 1; index > 0; index -= 1) {
		const swapIndex = Math.floor(random() * (index + 1));
		[order[index], order[swapIndex]] = [order[swapIndex], order[index]];
	}
	return order;
}
