/**
 * Tests for lib/pagination.ts
 *
 * These tests validate:
 * 1. normalizeListResponse correctly handles different API response formats
 * 2. Edge cases and malformed data are handled gracefully
 */

import { describe, it, expect } from "vitest";
import { normalizeListResponse, type ListResponse } from "@/lib/pagination";

describe("normalizeListResponse", () => {
	describe("Case 1: Already in desired shape { items, total }", () => {
		it("should pass through correctly shaped response", () => {
			const payload = {
				items: [{ id: 1 }, { id: 2 }],
				total: 10,
			};

			const result = normalizeListResponse<{ id: number }>(payload);

			expect(result.items).toEqual([{ id: 1 }, { id: 2 }]);
			expect(result.total).toBe(10);
		});

		it("should use items length if total is missing", () => {
			const payload = {
				items: [{ id: 1 }, { id: 2 }, { id: 3 }],
			};

			const result = normalizeListResponse(payload);

			expect(result.items.length).toBe(3);
			expect(result.total).toBe(3);
		});

		it("should handle empty items array", () => {
			const payload = {
				items: [],
				total: 0,
			};

			const result = normalizeListResponse(payload);

			expect(result.items).toEqual([]);
			expect(result.total).toBe(0);
		});
	});

	describe("Case 2: Tuple format [items, total]", () => {
		it("should normalize tuple response", () => {
			const payload = [[{ id: 1 }, { id: 2 }], 100];

			const result = normalizeListResponse<{ id: number }>(payload);

			expect(result.items).toEqual([{ id: 1 }, { id: 2 }]);
			expect(result.total).toBe(100);
		});

		it("should use items length if total is not a number in tuple", () => {
			const payload = [[{ id: 1 }, { id: 2 }], "invalid"];

			const result = normalizeListResponse(payload);

			expect(result.items.length).toBe(2);
			expect(result.total).toBe(2);
		});

		it("should handle empty tuple array", () => {
			const payload = [[], 0];

			const result = normalizeListResponse(payload);

			expect(result.items).toEqual([]);
			expect(result.total).toBe(0);
		});
	});

	describe("Case 3: Plain array", () => {
		it("should normalize plain array response", () => {
			const payload = [{ id: 1 }, { id: 2 }, { id: 3 }];

			const result = normalizeListResponse<{ id: number }>(payload);

			expect(result.items).toEqual(payload);
			expect(result.total).toBe(3);
		});

		it("should handle empty plain array", () => {
			const payload: unknown[] = [];

			const result = normalizeListResponse(payload);

			expect(result.items).toEqual([]);
			expect(result.total).toBe(0);
		});
	});

	describe("Edge cases and error handling", () => {
		it("should return empty result for null payload", () => {
			const result = normalizeListResponse(null);

			expect(result.items).toEqual([]);
			expect(result.total).toBe(0);
		});

		it("should return empty result for undefined payload", () => {
			const result = normalizeListResponse(undefined);

			expect(result.items).toEqual([]);
			expect(result.total).toBe(0);
		});

		it("should return empty result for string payload", () => {
			const result = normalizeListResponse("invalid");

			expect(result.items).toEqual([]);
			expect(result.total).toBe(0);
		});

		it("should return empty result for number payload", () => {
			const result = normalizeListResponse(123);

			expect(result.items).toEqual([]);
			expect(result.total).toBe(0);
		});

		it("should return empty result for object without items", () => {
			const result = normalizeListResponse({ data: [1, 2, 3] });

			expect(result.items).toEqual([]);
			expect(result.total).toBe(0);
		});

		it("should handle tuple with null first element", () => {
			const payload = [null, 5];

			const result = normalizeListResponse(payload);

			// This should fall through to plain array handling
			expect(result).toBeDefined();
		});
	});

	describe("Type preservation", () => {
		interface User {
			id: number;
			name: string;
		}

		it("should preserve typed items", () => {
			const payload = {
				items: [
					{ id: 1, name: "Alice" },
					{ id: 2, name: "Bob" },
				],
				total: 2,
			};

			const result: ListResponse<User> = normalizeListResponse<User>(payload);

			expect(result.items[0].name).toBe("Alice");
			expect(result.items[1].id).toBe(2);
		});
	});
});
