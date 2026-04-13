import { WhaleActivityFeed, type WhaleTransaction } from "../whale/WhaleActivityFeed";

export interface WhaleActivityWidgetProps {
    /** List of whale transactions */
    transactions: WhaleTransaction[];
    /** Callback when a wallet is tracked */
    onTrackWallet?: (address: string) => void;
    /** Callback when a transaction is viewed */
    onViewTransaction?: (txHash: string) => void;
}

/**
 * WhaleActivityWidget - Inline whale activity display in chat
 * Wraps WhaleActivityFeed for conversational UX
 */
export function WhaleActivityWidget({
    transactions,
    onTrackWallet,
    onViewTransaction,
}: WhaleActivityWidgetProps) {
    return (
        <div className="my-3">
            <WhaleActivityFeed
                transactions={transactions}
                onTrackWallet={onTrackWallet}
                onViewTransaction={onViewTransaction}
            />
        </div>
    );
}

