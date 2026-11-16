declare module "fuzzy-search" {
	interface FuzzySearchOptions {
		caseSensitive?: boolean;
		sort?: boolean;
	}

	class FuzzySearch<T> {
		constructor(haystack: T[], keys?: string[], options?: FuzzySearchOptions);
		search(needle: string): T[];
	}

	export default FuzzySearch;
}
