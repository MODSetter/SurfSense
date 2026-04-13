import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { MOCK_TOKEN_DATA, MOCK_MODE } from "../mock/mockData";

/**
 * Page context types
 */
export type PageType = "dexscreener" | "coingecko" | "twitter" | "generic";

export interface TokenData {
    chain: string;
    pairAddress: string;
    tokenSymbol?: string;
    tokenName?: string;
    price?: string;
    priceChange24h?: number;
    volume24h?: string;
    liquidity?: string;
    marketCap?: string;
}

export interface PageContext {
    url: string;
    title: string;
    pageType: PageType;
    tokenData?: TokenData;
    /** Detected tokens from page content (Twitter mentions, addresses, pairs) */
    detectedTokens?: TokenData[];
}

interface PageContextValue {
    context: PageContext | null;
    updateContext: (context: PageContext) => void;
    /** Whether we're using mock data */
    isMockMode: boolean;
}

const PageContextContext = createContext<PageContextValue>({
    context: null,
    updateContext: () => { },
    isMockMode: false,
});

export function usePageContext() {
    return useContext(PageContextContext);
}

/**
 * Provider for page context detection
 * Listens to messages from content scripts
 * Uses mock data in development mode
 */
export function PageContextProvider({ children }: { children: ReactNode }) {
    const [context, setContext] = useState<PageContext | null>(null);
    const isMockMode = MOCK_MODE.enabled;

    useEffect(() => {
        // Use mock data in development mode
        if (MOCK_MODE.enabled && MOCK_MODE.simulateDexScreener) {
            setContext({
                url: "https://dexscreener.com/solana/7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
                title: "BULLA / SOL | DEX Screener",
                pageType: "dexscreener",
                tokenData: MOCK_TOKEN_DATA,
            });
            return;
        }

        // Listen for page context updates from content script
        const handleMessage = (message: any) => {
            if (message.type === "PAGE_CONTEXT_UPDATE") {
                setContext(message.data);
            }
        };

        chrome.runtime.onMessage.addListener(handleMessage);

        // Request initial context
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]?.id) {
                chrome.tabs.sendMessage(tabs[0].id, { type: "GET_PAGE_CONTEXT" });
            }
        });

        return () => {
            chrome.runtime.onMessage.removeListener(handleMessage);
        };
    }, []);

    return (
        <PageContextContext.Provider value={{ context, updateContext: setContext, isMockMode }}>
            {children}
        </PageContextContext.Provider>
    );
}
