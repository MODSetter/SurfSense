/**
 * Vitest test setup file.
 *
 * This file runs before all tests and sets up the testing environment.
 */

import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Mock localStorage for auth-utils tests
const localStorageMock = {
	store: {} as Record<string, string>,
	getItem: vi.fn((key: string) => localStorageMock.store[key] ?? null),
	setItem: vi.fn((key: string, value: string) => {
		localStorageMock.store[key] = value;
	}),
	removeItem: vi.fn((key: string) => {
		delete localStorageMock.store[key];
	}),
	clear: vi.fn(() => {
		localStorageMock.store = {};
	}),
};

Object.defineProperty(window, "localStorage", {
	value: localStorageMock,
});

// Mock window.location
const locationMock = {
	href: "",
	pathname: "/dashboard",
	search: "",
	hash: "",
};

Object.defineProperty(window, "location", {
	value: locationMock,
	writable: true,
});

// Mock Next.js router
vi.mock("next/navigation", () => ({
	useRouter: () => ({
		push: vi.fn(),
		replace: vi.fn(),
		prefetch: vi.fn(),
		back: vi.fn(),
		forward: vi.fn(),
	}),
	usePathname: () => "/",
	useSearchParams: () => new URLSearchParams(),
	useParams: () => ({}),
}));

// Mock Next.js Image component
vi.mock("next/image", () => ({
	default: ({
		src,
		alt,
		className,
		...props
	}: {
		src: string;
		alt: string;
		className?: string;
		[key: string]: unknown;
	}) => {
		// eslint-disable-next-line @next/next/no-img-element
		return <img src={src} alt={alt} className={className} {...props} />;
	},
}));

// Mock Next.js Link component
vi.mock("next/link", () => ({
	default: ({
		children,
		href,
		...props
	}: {
		children: React.ReactNode;
		href: string;
		[key: string]: unknown;
	}) => {
		return (
			<a href={href} {...props}>
				{children}
			</a>
		);
	},
}));

// Mock window.matchMedia for responsive components
Object.defineProperty(window, "matchMedia", {
	writable: true,
	value: vi.fn().mockImplementation((query: string) => ({
		matches: false,
		media: query,
		onchange: null,
		addListener: vi.fn(),
		removeListener: vi.fn(),
		addEventListener: vi.fn(),
		removeEventListener: vi.fn(),
		dispatchEvent: vi.fn(),
	})),
});

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
	observe: vi.fn(),
	unobserve: vi.fn(),
	disconnect: vi.fn(),
}));

// Mock IntersectionObserver
global.IntersectionObserver = vi.fn().mockImplementation(() => ({
	observe: vi.fn(),
	unobserve: vi.fn(),
	disconnect: vi.fn(),
}));

// Clean up after each test
afterEach(() => {
	vi.clearAllMocks();
	localStorageMock.clear();
	locationMock.href = "";
	locationMock.pathname = "/dashboard";
	locationMock.search = "";
	locationMock.hash = "";
});
