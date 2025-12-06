/**
 * Tests for hooks/use-media-query.ts and hooks/use-mobile.ts
 *
 * These tests validate:
 * 1. Media query hook responds to viewport changes
 * 2. Mobile detection works correctly at breakpoints
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useIsMobile } from "@/hooks/use-mobile";

describe("useMediaQuery", () => {
	let mockMatchMedia: ReturnType<typeof vi.fn>;
	let mockAddEventListener: ReturnType<typeof vi.fn>;
	let mockRemoveEventListener: ReturnType<typeof vi.fn>;
	let changeHandler: ((event: MediaQueryListEvent) => void) | null = null;

	beforeEach(() => {
		mockAddEventListener = vi.fn((event, handler) => {
			if (event === "change") {
				changeHandler = handler;
			}
		});
		mockRemoveEventListener = vi.fn();

		mockMatchMedia = vi.fn().mockImplementation((query: string) => ({
			matches: false,
			media: query,
			onchange: null,
			addEventListener: mockAddEventListener,
			removeEventListener: mockRemoveEventListener,
			addListener: vi.fn(),
			removeListener: vi.fn(),
			dispatchEvent: vi.fn(),
		}));

		Object.defineProperty(window, "matchMedia", {
			writable: true,
			value: mockMatchMedia,
		});

		changeHandler = null;
	});

	it("should return false by default", () => {
		const { result } = renderHook(() => useMediaQuery("(min-width: 768px)"));

		expect(result.current).toBe(false);
	});

	it("should return true when media query matches", () => {
		mockMatchMedia.mockImplementation((query: string) => ({
			matches: true,
			media: query,
			addEventListener: mockAddEventListener,
			removeEventListener: mockRemoveEventListener,
		}));

		const { result } = renderHook(() => useMediaQuery("(min-width: 768px)"));

		expect(result.current).toBe(true);
	});

	it("should add event listener on mount", () => {
		renderHook(() => useMediaQuery("(min-width: 768px)"));

		expect(mockAddEventListener).toHaveBeenCalledWith("change", expect.any(Function));
	});

	it("should remove event listener on unmount", () => {
		const { unmount } = renderHook(() => useMediaQuery("(min-width: 768px)"));

		unmount();

		expect(mockRemoveEventListener).toHaveBeenCalledWith("change", expect.any(Function));
	});

	it("should update when media query changes", () => {
		const { result } = renderHook(() => useMediaQuery("(min-width: 768px)"));

		expect(result.current).toBe(false);

		// Simulate media query change
		act(() => {
			if (changeHandler) {
				changeHandler({ matches: true } as MediaQueryListEvent);
			}
		});

		expect(result.current).toBe(true);
	});

	it("should re-subscribe when query changes", () => {
		const { rerender } = renderHook(({ query }) => useMediaQuery(query), {
			initialProps: { query: "(min-width: 768px)" },
		});

		expect(mockMatchMedia).toHaveBeenCalledWith("(min-width: 768px)");

		rerender({ query: "(min-width: 1024px)" });

		expect(mockMatchMedia).toHaveBeenCalledWith("(min-width: 1024px)");
	});
});

describe("useIsMobile", () => {
	let mockMatchMedia: ReturnType<typeof vi.fn>;
	let mockAddEventListener: ReturnType<typeof vi.fn>;
	let mockRemoveEventListener: ReturnType<typeof vi.fn>;
	let changeHandler: (() => void) | null = null;

	beforeEach(() => {
		mockAddEventListener = vi.fn((event, handler) => {
			if (event === "change") {
				changeHandler = handler;
			}
		});
		mockRemoveEventListener = vi.fn();

		mockMatchMedia = vi.fn().mockImplementation(() => ({
			matches: false,
			addEventListener: mockAddEventListener,
			removeEventListener: mockRemoveEventListener,
		}));

		Object.defineProperty(window, "matchMedia", {
			writable: true,
			value: mockMatchMedia,
		});

		// Default to desktop width
		Object.defineProperty(window, "innerWidth", {
			writable: true,
			value: 1024,
		});

		changeHandler = null;
	});

	it("should return false for desktop width (>= 768px)", () => {
		Object.defineProperty(window, "innerWidth", { value: 1024, writable: true });

		const { result } = renderHook(() => useIsMobile());

		expect(result.current).toBe(false);
	});

	it("should return true for mobile width (< 768px)", () => {
		Object.defineProperty(window, "innerWidth", { value: 500, writable: true });

		const { result } = renderHook(() => useIsMobile());

		expect(result.current).toBe(true);
	});

	it("should return false at exactly 768px (breakpoint)", () => {
		Object.defineProperty(window, "innerWidth", { value: 768, writable: true });

		const { result } = renderHook(() => useIsMobile());

		expect(result.current).toBe(false);
	});

	it("should return true at 767px (just below breakpoint)", () => {
		Object.defineProperty(window, "innerWidth", { value: 767, writable: true });

		const { result } = renderHook(() => useIsMobile());

		expect(result.current).toBe(true);
	});

	it("should update when window is resized", () => {
		Object.defineProperty(window, "innerWidth", { value: 1024, writable: true });

		const { result } = renderHook(() => useIsMobile());

		expect(result.current).toBe(false);

		// Simulate resize to mobile
		act(() => {
			Object.defineProperty(window, "innerWidth", { value: 500, writable: true });
			if (changeHandler) {
				changeHandler();
			}
		});

		expect(result.current).toBe(true);
	});

	it("should clean up event listener on unmount", () => {
		const { unmount } = renderHook(() => useIsMobile());

		unmount();

		expect(mockRemoveEventListener).toHaveBeenCalledWith("change", expect.any(Function));
	});
});
