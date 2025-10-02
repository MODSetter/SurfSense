// Helper to normalize list responses from the API
// Supports shapes: Array<T>, { items: T[]; total: number }, and tuple [T[], total]
export type ListResponse<T> = {
	items: T[];
	total: number;
};

export function normalizeListResponse<T>(payload: any): ListResponse<T> {
	try {
		// Case 1: already in desired shape
		if (payload && Array.isArray(payload.items)) {
			const total = typeof payload.total === "number" ? payload.total : payload.items.length;
			return { items: payload.items as T[], total };
		}

		// Case 2: tuple [items, total]
		if (Array.isArray(payload) && payload.length === 2 && Array.isArray(payload[0])) {
			const items = (payload[0] ?? []) as T[];
			const rawTotal = payload[1];
			const total = typeof rawTotal === "number" ? rawTotal : items.length;
			return { items, total };
		}

		// Case 3: plain array
		if (Array.isArray(payload)) {
			return { items: payload as T[], total: (payload as T[]).length };
		}
	} catch (e) {
		// fallthrough to default
	}

	return { items: [], total: 0 };
}
