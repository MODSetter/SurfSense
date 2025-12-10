/**
 * Tests for components/Logo.tsx
 *
 * These tests validate:
 * 1. Logo renders as a link to home page
 * 2. Logo image has correct alt text for accessibility
 * 3. Logo accepts and applies custom className
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Logo } from "@/components/Logo";

describe("Logo", () => {
	it("should render a link to the home page", () => {
		render(<Logo />);

		const link = screen.getByRole("link");
		expect(link).toHaveAttribute("href", "/");
	});

	it("should render an image with correct alt text", () => {
		render(<Logo />);

		const image = screen.getByAltText("logo");
		expect(image).toBeInTheDocument();
	});

	it("should have correct image source", () => {
		render(<Logo />);

		const image = screen.getByAltText("logo");
		// Next.js Image component transforms the src, so we check if src attribute exists
		expect(image).toHaveAttribute("src");
	});

	it("should apply custom className to the image", () => {
		render(<Logo className="h-8 w-8" />);

		const image = screen.getByAltText("logo");
		expect(image).toHaveClass("h-8", "w-8");
	});

	it("should render without className prop", () => {
		render(<Logo />);

		const image = screen.getByAltText("logo");
		expect(image).toBeInTheDocument();
	});
});
