import type { PlasmoCSConfig, PlasmoGetInlineAnchor, PlasmoGetStyle } from "plasmo";
import { Sparkles, X } from "lucide-react";
import { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";

/**
 * Floating Quick Action Button (like Mevx)
 * Appears on crypto-related pages for quick token analysis
 */

export const config: PlasmoCSConfig = {
    matches: [
        "*://dexscreener.com/*",
        "*://www.dexscreener.com/*",
        "*://twitter.com/*",
        "*://x.com/*",
        "*://coingecko.com/*",
        "*://www.coingecko.com/*",
        "*://coinmarketcap.com/*",
        "*://www.coinmarketcap.com/*",
    ],
};

export const getStyle: PlasmoGetStyle = () => {
    const style = document.createElement("style");
    style.textContent = `
        #surfsense-floating-button {
            all: initial;
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 999999;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        
        #surfsense-floating-popup {
            all: initial;
            position: fixed;
            bottom: 88px;
            right: 24px;
            z-index: 999999;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
    `;
    return style;
};

interface TokenQuickInfo {
    symbol: string;
    name: string;
    price: string;
    change24h: number;
    chain: string;
}

function FloatingButton() {
    const [isOpen, setIsOpen] = useState(false);
    const [tokenInfo, setTokenInfo] = useState<TokenQuickInfo | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        // Listen for token detection from content script
        const handleMessage = (message: any) => {
            if (message.type === "TOKEN_DETECTED") {
                setTokenInfo(message.data);
            }
        };

        chrome.runtime.onMessage.addListener(handleMessage);
        return () => chrome.runtime.onMessage.removeListener(handleMessage);
    }, []);

    const handleButtonClick = async () => {
        if (!isOpen) {
            setIsLoading(true);
            // Simulate fetching quick token info
            setTimeout(() => {
                setTokenInfo({
                    symbol: "BONK",
                    name: "Bonk",
                    price: "$0.00001234",
                    change24h: 156.7,
                    chain: "Solana",
                });
                setIsLoading(false);
            }, 500);
        }
        setIsOpen(!isOpen);
    };

    const handleOpenSidepanel = () => {
        chrome.runtime.sendMessage({ type: "OPEN_SIDEPANEL" });
        setIsOpen(false);
    };

    return (
        <>
            {/* Floating Button */}
            <div id="surfsense-floating-button">
                <button
                    onClick={handleButtonClick}
                    style={{
                        width: "56px",
                        height: "56px",
                        borderRadius: "50%",
                        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                        border: "none",
                        boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        transition: "all 0.2s ease",
                        color: "white",
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.transform = "scale(1.1)";
                        e.currentTarget.style.boxShadow = "0 6px 16px rgba(0, 0, 0, 0.2)";
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.transform = "scale(1)";
                        e.currentTarget.style.boxShadow = "0 4px 12px rgba(0, 0, 0, 0.15)";
                    }}
                >
                    {isOpen ? <X size={24} /> : <Sparkles size={24} />}
                </button>
            </div>

            {/* Quick Info Popup */}
            {isOpen && (
                <div id="surfsense-floating-popup">
                    <div
                        style={{
                            width: "320px",
                            background: "white",
                            borderRadius: "12px",
                            boxShadow: "0 8px 24px rgba(0, 0, 0, 0.15)",
                            padding: "16px",
                            border: "1px solid #e5e7eb",
                        }}
                    >
                        {isLoading ? (
                            <div style={{ textAlign: "center", padding: "20px", color: "#6b7280" }}>
                                Loading...
                            </div>
                        ) : tokenInfo ? (
                            <>
                                <div style={{ marginBottom: "12px" }}>
                                    <div style={{ fontSize: "18px", fontWeight: "600", color: "#111827" }}>
                                        {tokenInfo.symbol}
                                    </div>
                                    <div style={{ fontSize: "14px", color: "#6b7280" }}>{tokenInfo.name}</div>
                                </div>
                                <div style={{ marginBottom: "16px" }}>
                                    <div style={{ fontSize: "24px", fontWeight: "700", color: "#111827" }}>
                                        {tokenInfo.price}
                                    </div>
                                    <div
                                        style={{
                                            fontSize: "14px",
                                            color: tokenInfo.change24h >= 0 ? "#10b981" : "#ef4444",
                                            fontWeight: "500",
                                        }}
                                    >
                                        {tokenInfo.change24h >= 0 ? "+" : ""}
                                        {tokenInfo.change24h.toFixed(2)}% (24h)
                                    </div>
                                </div>
                                <button
                                    onClick={handleOpenSidepanel}
                                    style={{
                                        width: "100%",
                                        padding: "10px",
                                        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                                        color: "white",
                                        border: "none",
                                        borderRadius: "8px",
                                        fontSize: "14px",
                                        fontWeight: "500",
                                        cursor: "pointer",
                                        transition: "opacity 0.2s",
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.opacity = "0.9";
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.opacity = "1";
                                    }}
                                >
                                    Full Analysis
                                </button>
                            </>
                        ) : (
                            <div style={{ textAlign: "center", padding: "20px", color: "#6b7280" }}>
                                No token detected
                            </div>
                        )}
                    </div>
                </div>
            )}
        </>
    );
}

export default FloatingButton;

