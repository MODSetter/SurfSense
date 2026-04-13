import { ThreadGeneratorPanel, type GeneratedThread } from "../content/ThreadGeneratorPanel";

export interface ThreadGeneratorWidgetProps {
    /** Current token info */
    tokenAddress?: string;
    tokenSymbol?: string;
    chain?: string;
    /** Generated thread (if available) */
    generatedThread?: GeneratedThread;
    /** Callback when thread is generated */
    onGenerate?: (request: any) => void;
    /** Callback when thread is exported */
    onExport?: (format: "copy" | "twitter") => void;
}

/**
 * ThreadGeneratorWidget - Inline thread generator in chat
 * Wraps ThreadGeneratorPanel for conversational UX
 */
export function ThreadGeneratorWidget({
    tokenAddress,
    tokenSymbol,
    chain,
    generatedThread,
    onGenerate,
    onExport,
}: ThreadGeneratorWidgetProps) {
    return (
        <div className="my-3 max-h-[600px] overflow-hidden rounded-lg border">
            <ThreadGeneratorPanel
                tokenAddress={tokenAddress}
                tokenSymbol={tokenSymbol}
                chain={chain}
                onGenerate={onGenerate}
                onExport={onExport}
            />
        </div>
    );
}

