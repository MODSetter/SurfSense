/**
 * Tests for lib/auth-utils.ts
 *
 * These tests validate:
 * 1. Token storage and retrieval works correctly
 * 2. Authentication state is properly tracked
 * 3. Redirect path handling for post-login navigation
 * 4. Auth headers are correctly constructed
 */

import { describe, it, expect, beforeEach } from "vitest";
import {
	getBearerToken,
	setBearerToken,
	clearBearerToken,
	isAuthenticated,
	getAndClearRedirectPath,
	getAuthHeaders,
} from "@/lib/auth-utils";

describe("Token Management", () => {
	beforeEach(() => {
		// Clear localStorage before each test
		window.localStorage.clear();
	});

	describe("getBearerToken", () => {
		it("should return null when no token is stored", () => {
			const token = getBearerToken();
			expect(token).toBeNull();
		});

		it("should return the stored token", () => {
			window.localStorage.setItem("surfsense_bearer_token", "test-token-123");

			const token = getBearerToken();
			expect(token).toBe("test-token-123");
		});
	});

	describe("setBearerToken", () => {
		it("should store the token in localStorage", () => {
			setBearerToken("my-auth-token");

			expect(window.localStorage.getItem("surfsense_bearer_token")).toBe("my-auth-token");
		});

		it("should overwrite existing token", () => {
			setBearerToken("old-token");
			setBearerToken("new-token");

			expect(window.localStorage.getItem("surfsense_bearer_token")).toBe("new-token");
		});
	});

	describe("clearBearerToken", () => {
		it("should remove the token from localStorage", () => {
			window.localStorage.setItem("surfsense_bearer_token", "token-to-clear");

			clearBearerToken();

			expect(window.localStorage.getItem("surfsense_bearer_token")).toBeNull();
		});

		it("should not throw when no token exists", () => {
			expect(() => clearBearerToken()).not.toThrow();
		});
	});
});

describe("Authentication State", () => {
	beforeEach(() => {
		window.localStorage.clear();
	});

	describe("isAuthenticated", () => {
		it("should return false when no token exists", () => {
			expect(isAuthenticated()).toBe(false);
		});

		it("should return true when token exists", () => {
			window.localStorage.setItem("surfsense_bearer_token", "valid-token");

			expect(isAuthenticated()).toBe(true);
		});

		it("should return false after token is cleared", () => {
			window.localStorage.setItem("surfsense_bearer_token", "valid-token");
			expect(isAuthenticated()).toBe(true);

			clearBearerToken();
			expect(isAuthenticated()).toBe(false);
		});
	});
});

describe("Redirect Path Handling", () => {
	beforeEach(() => {
		window.localStorage.clear();
	});

	describe("getAndClearRedirectPath", () => {
		it("should return null when no redirect path is stored", () => {
			const path = getAndClearRedirectPath();
			expect(path).toBeNull();
		});

		it("should return and clear stored redirect path", () => {
			window.localStorage.setItem("surfsense_redirect_path", "/dashboard/settings");

			const path = getAndClearRedirectPath();

			expect(path).toBe("/dashboard/settings");
			expect(window.localStorage.getItem("surfsense_redirect_path")).toBeNull();
		});

		it("should only return path once (cleared after first read)", () => {
			window.localStorage.setItem("surfsense_redirect_path", "/some/path");

			const firstRead = getAndClearRedirectPath();
			const secondRead = getAndClearRedirectPath();

			expect(firstRead).toBe("/some/path");
			expect(secondRead).toBeNull();
		});
	});
});

describe("Auth Headers", () => {
	beforeEach(() => {
		window.localStorage.clear();
	});

	describe("getAuthHeaders", () => {
		it("should return empty object when no token exists", () => {
			const headers = getAuthHeaders();

			expect(headers).toEqual({});
		});

		it("should return Authorization header when token exists", () => {
			window.localStorage.setItem("surfsense_bearer_token", "my-token");

			const headers = getAuthHeaders();

			expect(headers).toEqual({
				Authorization: "Bearer my-token",
			});
		});

		it("should merge additional headers with auth header", () => {
			window.localStorage.setItem("surfsense_bearer_token", "my-token");

			const headers = getAuthHeaders({
				"Content-Type": "application/json",
				"X-Custom": "value",
			});

			expect(headers).toEqual({
				Authorization: "Bearer my-token",
				"Content-Type": "application/json",
				"X-Custom": "value",
			});
		});

		it("should return only additional headers when no token", () => {
			const headers = getAuthHeaders({
				"Content-Type": "application/json",
			});

			expect(headers).toEqual({
				"Content-Type": "application/json",
			});
		});

		it("should handle undefined additional headers", () => {
			window.localStorage.setItem("surfsense_bearer_token", "my-token");

			const headers = getAuthHeaders(undefined);

			expect(headers).toEqual({
				Authorization: "Bearer my-token",
			});
		});
	});
});

describe("Token Format Validation", () => {
	beforeEach(() => {
		window.localStorage.clear();
	});

	it("should handle tokens with special characters", () => {
		const specialToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ";

		setBearerToken(specialToken);
		const retrieved = getBearerToken();

		expect(retrieved).toBe(specialToken);
	});

	it("should handle empty string token", () => {
		setBearerToken("");
		const retrieved = getBearerToken();

		expect(retrieved).toBe("");
		// Empty string is falsy, so isAuthenticated should return false
		expect(isAuthenticated()).toBe(false);
	});
});
