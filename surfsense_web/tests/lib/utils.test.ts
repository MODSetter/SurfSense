/**
 * Tests for lib/utils.ts
 *
 * These tests validate:
 * 1. cn() correctly merges Tailwind classes
 * 2. getChatTitleFromMessages() extracts titles correctly
 */

import { describe, it, expect } from "vitest";
import { cn, getChatTitleFromMessages } from "@/lib/utils";

describe("cn - Class Name Merger", () => {
	it("should merge simple class names", () => {
		const result = cn("foo", "bar");
		expect(result).toBe("foo bar");
	});

	it("should handle conditional classes", () => {
		const isActive = true;
		const result = cn("base", isActive && "active");
		expect(result).toBe("base active");
	});

	it("should filter out falsy values", () => {
		const result = cn("base", false, null, undefined, "valid");
		expect(result).toBe("base valid");
	});

	it("should merge conflicting Tailwind classes (last wins)", () => {
		// tailwind-merge should resolve conflicts
		const result = cn("p-4", "p-2");
		expect(result).toBe("p-2");
	});

	it("should handle object syntax", () => {
		const result = cn({
			base: true,
			active: true,
			disabled: false,
		});
		expect(result).toContain("base");
		expect(result).toContain("active");
		expect(result).not.toContain("disabled");
	});

	it("should handle array syntax", () => {
		const result = cn(["foo", "bar"]);
		expect(result).toBe("foo bar");
	});

	it("should handle empty input", () => {
		const result = cn();
		expect(result).toBe("");
	});

	it("should handle Tailwind responsive prefixes correctly", () => {
		const result = cn("text-sm", "md:text-lg", "lg:text-xl");
		expect(result).toBe("text-sm md:text-lg lg:text-xl");
	});

	it("should merge color classes properly", () => {
		const result = cn("text-red-500", "text-blue-500");
		expect(result).toBe("text-blue-500");
	});
});

describe("getChatTitleFromMessages", () => {
	it("should return first user message content as title", () => {
		const messages = [
			{ id: "1", role: "user" as const, content: "Hello, how are you?" },
			{ id: "2", role: "assistant" as const, content: "I am fine, thank you!" },
		];

		const title = getChatTitleFromMessages(messages);
		expect(title).toBe("Hello, how are you?");
	});

	it("should return 'Untitled Chat' when no user messages", () => {
		const messages = [
			{ id: "1", role: "assistant" as const, content: "Hello!" },
			{ id: "2", role: "system" as const, content: "You are a helpful assistant" },
		];

		const title = getChatTitleFromMessages(messages);
		expect(title).toBe("Untitled Chat");
	});

	it("should return 'Untitled Chat' for empty messages array", () => {
		const title = getChatTitleFromMessages([]);
		expect(title).toBe("Untitled Chat");
	});

	it("should use first user message even if there are multiple", () => {
		const messages = [
			{ id: "1", role: "assistant" as const, content: "Welcome!" },
			{ id: "2", role: "user" as const, content: "First question" },
			{ id: "3", role: "assistant" as const, content: "Answer" },
			{ id: "4", role: "user" as const, content: "Second question" },
		];

		const title = getChatTitleFromMessages(messages);
		expect(title).toBe("First question");
	});

	it("should handle messages with only system role", () => {
		const messages = [{ id: "1", role: "system" as const, content: "System prompt" }];

		const title = getChatTitleFromMessages(messages);
		expect(title).toBe("Untitled Chat");
	});
});
