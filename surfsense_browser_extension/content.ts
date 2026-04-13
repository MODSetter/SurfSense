import type { PlasmoCSConfig } from "plasmo";

export const config: PlasmoCSConfig = {
	matches: ["<all_urls>"],
	all_frames: true,
	world: "MAIN",
};

/**
 * Content script for page context detection
 * Extracts relevant data from crypto pages and sends to side panel
 */

type PageType = "dexscreener" | "coingecko" | "twitter" | "generic";

interface TokenData {
	chain: string;
	pairAddress: string;
	tokenSymbol?: string;
	price?: string;
	volume24h?: string;
	liquidity?: string;
}

interface PageContext {
	url: string;
	title: string;
	pageType: PageType;
	tokenData?: TokenData;
}

/**
 * Detect page type from URL
 */
function detectPageType(url: string): PageType {
	if (url.includes("dexscreener.com")) return "dexscreener";
	if (url.includes("coingecko.com")) return "coingecko";
	if (url.includes("twitter.com") || url.includes("x.com")) return "twitter";
	return "generic";
}

/**
 * Extract DexScreener token data from DOM
 */
function extractDexScreenerData(): TokenData | undefined {
	const url = window.location.href;
	const match = url.match(/dexscreener\.com\/([^\/]+)\/([^\/\?]+)/);

	if (!match) return undefined;

	const [, chain, pairAddress] = match;

	// Try to extract data from DOM
	// Note: DexScreener uses dynamic rendering, so selectors may need adjustment
	const tokenSymbol =
		document.querySelector('[data-test="token-symbol"]')?.textContent ||
		document.querySelector(".token-symbol")?.textContent ||
		undefined;

	const price =
		document.querySelector('[data-test="token-price"]')?.textContent ||
		document.querySelector(".token-price")?.textContent ||
		undefined;

	const volume24h =
		document.querySelector('[data-test="volume-24h"]')?.textContent ||
		document.querySelector(".volume-24h")?.textContent ||
		undefined;

	const liquidity =
		document.querySelector('[data-test="liquidity"]')?.textContent ||
		document.querySelector(".liquidity")?.textContent ||
		undefined;

	return {
		chain,
		pairAddress,
		tokenSymbol,
		price,
		volume24h,
		liquidity,
	};
}

/**
 * Extract token mentions from Twitter/X
 * Detects $TOKEN format (e.g., $BONK, $SOL)
 */
function extractTwitterTokens(): TokenData[] {
	const tokens: TokenData[] = [];
	const pageText = document.body.innerText;

	// Match $TOKEN pattern (e.g., $BONK, $SOL, $PEPE)
	const tokenPattern = /\$([A-Z]{2,10})\b/g;
	const matches = pageText.matchAll(tokenPattern);

	const uniqueTokens = new Set<string>();
	for (const match of matches) {
		const symbol = match[1];
		if (!uniqueTokens.has(symbol)) {
			uniqueTokens.add(symbol);
			tokens.push({
				chain: "solana", // Default to Solana, can be enhanced
				pairAddress: "", // Will be resolved via API
				tokenSymbol: symbol,
			});
		}
	}

	return tokens;
}

/**
 * Extract contract addresses from page content
 * Supports Solana and Ethereum address formats
 */
function extractContractAddresses(): TokenData[] {
	const tokens: TokenData[] = [];
	const pageText = document.body.innerText;

	// Solana address pattern (base58, 32-44 characters)
	const solanaPattern = /\b([1-9A-HJ-NP-Za-km-z]{32,44})\b/g;

	// Ethereum address pattern (0x followed by 40 hex characters)
	const ethPattern = /\b(0x[a-fA-F0-9]{40})\b/g;

	// Extract Ethereum addresses
	const ethMatches = pageText.matchAll(ethPattern);
	for (const match of ethMatches) {
		const address = match[1];
		tokens.push({
			chain: "ethereum",
			pairAddress: address,
			tokenSymbol: undefined,
		});
	}

	// Extract Solana addresses (more selective to avoid false positives)
	const solanaMatches = pageText.matchAll(solanaPattern);
	const uniqueSolanaAddresses = new Set<string>();

	for (const match of solanaMatches) {
		const address = match[1];
		// Basic validation: should not be all same character, should have variety
		if (address.length >= 32 &&
		    address.length <= 44 &&
		    new Set(address).size > 10 &&
		    !uniqueSolanaAddresses.has(address)) {
			uniqueSolanaAddresses.add(address);
			tokens.push({
				chain: "solana",
				pairAddress: address,
				tokenSymbol: undefined,
			});
		}
	}

	return tokens.slice(0, 5); // Limit to first 5 to avoid spam
}

/**
 * Extract trading pairs from page content
 * Detects patterns like TOKEN/SOL, TOKEN/USDT, etc.
 */
function extractTradingPairs(): TokenData[] {
	const tokens: TokenData[] = [];
	const pageText = document.body.innerText;

	// Match trading pair patterns (e.g., BONK/SOL, PEPE/USDT)
	const pairPattern = /\b([A-Z]{2,10})\/([A-Z]{2,10})\b/g;
	const matches = pageText.matchAll(pairPattern);

	const uniquePairs = new Set<string>();
	for (const match of matches) {
		const baseToken = match[1];
		const quoteToken = match[2];
		const pairKey = `${baseToken}/${quoteToken}`;

		if (!uniquePairs.has(pairKey)) {
			uniquePairs.add(pairKey);
			tokens.push({
				chain: "solana", // Default to Solana
				pairAddress: "", // Will be resolved via API
				tokenSymbol: baseToken,
			});
		}
	}

	return tokens.slice(0, 3); // Limit to first 3 pairs
}

interface PageContext {
	url: string;
	title: string;
	pageType: PageType;
	tokenData?: TokenData;
	/** Detected tokens from page content (Twitter mentions, addresses, pairs) */
	detectedTokens?: TokenData[];
}

/**
 * Extract page context based on page type
 */
function extractPageContext(): PageContext {
	const url = window.location.href;
	const title = document.title;
	const pageType = detectPageType(url);

	const context: PageContext = {
		url,
		title,
		pageType,
	};

	// Add page-specific data
	if (pageType === "dexscreener") {
		context.tokenData = extractDexScreenerData();
	} else if (pageType === "twitter") {
		// Extract Twitter token mentions
		const twitterTokens = extractTwitterTokens();
		const contractAddresses = extractContractAddresses();
		const tradingPairs = extractTradingPairs();

		// Combine all detected tokens
		context.detectedTokens = [
			...twitterTokens,
			...contractAddresses,
			...tradingPairs,
		];

		// Set primary token if available
		if (context.detectedTokens.length > 0) {
			context.tokenData = context.detectedTokens[0];
		}
	} else if (pageType === "generic") {
		// For generic pages, try to detect contract addresses and trading pairs
		const contractAddresses = extractContractAddresses();
		const tradingPairs = extractTradingPairs();

		context.detectedTokens = [
			...contractAddresses,
			...tradingPairs,
		];

		// Set primary token if available
		if (context.detectedTokens.length > 0) {
			context.tokenData = context.detectedTokens[0];
		}
	}

	return context;
}

/**
 * Send context update to side panel
 */
function sendContextUpdate() {
	const context = extractPageContext();
	chrome.runtime.sendMessage({
		type: "PAGE_CONTEXT_UPDATE",
		data: context,
	});
}

// Send initial context after page load
if (document.readyState === "complete") {
	sendContextUpdate();
} else {
	window.addEventListener("load", sendContextUpdate);
}

// Listen for context requests from side panel
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
	if (message.type === "GET_PAGE_CONTEXT") {
		sendContextUpdate();
	}
});

// Watch for DOM changes (for dynamic content like DexScreener)
const observer = new MutationObserver(() => {
	// Debounce updates
	clearTimeout((window as any).__contextUpdateTimeout);
	(window as any).__contextUpdateTimeout = setTimeout(sendContextUpdate, 1000);
});

observer.observe(document.body, {
	childList: true,
	subtree: true,
});
