/**
 * Tests for components/ui/button.tsx
 *
 * These tests validate:
 * 1. Button renders correctly with different variants
 * 2. Button renders correctly with different sizes
 * 3. Button handles click events
 * 4. Button supports asChild prop for composition
 * 5. Button applies custom classNames correctly
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Button, buttonVariants } from "@/components/ui/button";

describe("Button", () => {
	describe("rendering", () => {
		it("should render children correctly", () => {
			render(<Button>Click me</Button>);

			expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument();
		});

		it("should render as a button element by default", () => {
			render(<Button>Test</Button>);

			const button = screen.getByRole("button");
			expect(button.tagName).toBe("BUTTON");
		});

		it("should apply data-slot attribute", () => {
			render(<Button>Test</Button>);

			expect(screen.getByRole("button")).toHaveAttribute("data-slot", "button");
		});
	});

	describe("variants", () => {
		it("should apply default variant styles", () => {
			render(<Button variant="default">Default</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("bg-primary");
		});

		it("should apply destructive variant styles", () => {
			render(<Button variant="destructive">Delete</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("bg-destructive");
		});

		it("should apply outline variant styles", () => {
			render(<Button variant="outline">Outline</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("border");
			expect(button).toHaveClass("bg-background");
		});

		it("should apply secondary variant styles", () => {
			render(<Button variant="secondary">Secondary</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("bg-secondary");
		});

		it("should apply ghost variant styles", () => {
			render(<Button variant="ghost">Ghost</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("hover:bg-accent");
		});

		it("should apply link variant styles", () => {
			render(<Button variant="link">Link</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("underline-offset-4");
		});
	});

	describe("sizes", () => {
		it("should apply default size styles", () => {
			render(<Button size="default">Default Size</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("h-9");
		});

		it("should apply small size styles", () => {
			render(<Button size="sm">Small</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("h-8");
		});

		it("should apply large size styles", () => {
			render(<Button size="lg">Large</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("h-10");
		});

		it("should apply icon size styles", () => {
			render(<Button size="icon">🔍</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("size-9");
		});
	});

	describe("interactions", () => {
		it("should call onClick handler when clicked", () => {
			const handleClick = vi.fn();
			render(<Button onClick={handleClick}>Click me</Button>);

			fireEvent.click(screen.getByRole("button"));

			expect(handleClick).toHaveBeenCalledTimes(1);
		});

		it("should not call onClick when disabled", () => {
			const handleClick = vi.fn();
			render(
				<Button onClick={handleClick} disabled>
					Disabled
				</Button>
			);

			fireEvent.click(screen.getByRole("button"));

			expect(handleClick).not.toHaveBeenCalled();
		});

		it("should apply disabled styles", () => {
			render(<Button disabled>Disabled</Button>);

			const button = screen.getByRole("button");
			expect(button).toBeDisabled();
			expect(button).toHaveClass("disabled:pointer-events-none");
		});
	});

	describe("custom className", () => {
		it("should merge custom className with default styles", () => {
			render(<Button className="custom-class">Custom</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("custom-class");
			// Should still have base styles
			expect(button).toHaveClass("inline-flex");
		});

		it("should allow overriding default styles", () => {
			render(<Button className="rounded-full">Rounded</Button>);

			const button = screen.getByRole("button");
			expect(button).toHaveClass("rounded-full");
		});
	});

	describe("asChild prop", () => {
		it("should render as child element when asChild is true", () => {
			render(
				<Button asChild>
					<a href="/test">Link Button</a>
				</Button>
			);

			const link = screen.getByRole("link", { name: "Link Button" });
			expect(link).toBeInTheDocument();
			expect(link).toHaveAttribute("href", "/test");
		});
	});
});

describe("buttonVariants", () => {
	it("should be a function that returns className string", () => {
		const className = buttonVariants();
		expect(typeof className).toBe("string");
		expect(className.length).toBeGreaterThan(0);
	});

	it("should generate different classes for different variants", () => {
		const defaultClass = buttonVariants({ variant: "default" });
		const destructiveClass = buttonVariants({ variant: "destructive" });

		expect(defaultClass).not.toBe(destructiveClass);
		expect(defaultClass).toContain("bg-primary");
		expect(destructiveClass).toContain("bg-destructive");
	});

	it("should generate different classes for different sizes", () => {
		const defaultSize = buttonVariants({ size: "default" });
		const smallSize = buttonVariants({ size: "sm" });

		expect(defaultSize).not.toBe(smallSize);
		expect(defaultSize).toContain("h-9");
		expect(smallSize).toContain("h-8");
	});
});
