/**
 * Business's founding price, per person a year, from ADR 0080: $60 for the first person and
 * $60 for each further one, until sales justify more. Both pages read their figures from here,
 * so they cannot disagree.
 */

export const FIRST_PERSON_PRICE = 60;
export const FURTHER_PERSON_PRICE = 60;

/** The most people the self-serve checkout covers; more is an Enterprise deal. */
export const SELF_SERVE_PEOPLE = 15;

export function businessYearlyPrice(people: number): number {
	if (!Number.isInteger(people) || people < 1) {
		throw new RangeError(
			`a Business licence covers a whole number of people, at least 1: ${people}`
		);
	}
	return FIRST_PERSON_PRICE + FURTHER_PERSON_PRICE * (people - 1);
}

export function yearlyPriceLabel(dollars: number): string {
	return `$${dollars.toLocaleString("en-US")}`;
}

export const BUSINESS_PRICE_EXAMPLES = [1, 2, 5, 10, SELF_SERVE_PEOPLE].map((people) => ({
	people,
	price: yearlyPriceLabel(businessYearlyPrice(people)),
}));
