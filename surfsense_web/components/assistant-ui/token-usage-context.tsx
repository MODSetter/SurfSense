"use client";

import {
	createContext,
	type FC,
	type ReactNode,
	useCallback,
	useContext,
	useSyncExternalStore,
} from "react";

export interface TokenUsageData {
	prompt_tokens: number;
	completion_tokens: number;
	total_tokens: number;
	/**
	 * Total provider USD cost for this assistant turn, in micro-USD
	 * (1_000_000 = $1.00). Populated from LiteLLM's response_cost on
	 * the backend. Optional because pre-cost-credits messages persisted
	 * before the migration won't have it.
	 */
	cost_micros?: number;
	usage?: Record<
		string,
		{
			prompt_tokens: number;
			completion_tokens: number;
			total_tokens: number;
			cost_micros?: number;
		}
	>;
	model_breakdown?: Record<
		string,
		{
			prompt_tokens: number;
			completion_tokens: number;
			total_tokens: number;
			cost_micros?: number;
		}
	>;
}

type Listener = () => void;

class TokenUsageStore {
	private data = new Map<string, TokenUsageData>();
	private listeners = new Set<Listener>();

	get(messageId: string): TokenUsageData | undefined {
		return this.data.get(messageId);
	}

	set(messageId: string, usage: TokenUsageData): void {
		this.data.set(messageId, usage);
		this.notify();
	}

	rename(oldId: string, newId: string): void {
		const usage = this.data.get(oldId);
		if (usage) {
			this.data.delete(oldId);
			this.data.set(newId, usage);
			this.notify();
		}
	}

	clear(): void {
		this.data.clear();
		this.notify();
	}

	subscribe = (listener: Listener): (() => void) => {
		this.listeners.add(listener);
		return () => this.listeners.delete(listener);
	};

	private notify(): void {
		for (const l of this.listeners) l();
	}
}

const TokenUsageContext = createContext<TokenUsageStore | null>(null);

export const TokenUsageProvider: FC<{ store: TokenUsageStore; children: ReactNode }> = ({
	store,
	children,
}) => <TokenUsageContext.Provider value={store}>{children}</TokenUsageContext.Provider>;

export function useTokenUsageStore(): TokenUsageStore {
	const store = useContext(TokenUsageContext);
	if (!store) throw new Error("useTokenUsageStore must be used within TokenUsageProvider");
	return store;
}

export function useTokenUsage(messageId: string | undefined): TokenUsageData | undefined {
	const store = useContext(TokenUsageContext);
	const getSnapshot = useCallback(
		() => (store && messageId ? store.get(messageId) : undefined),
		[store, messageId]
	);
	const subscribe = useCallback(
		(onStoreChange: () => void) => (store ? store.subscribe(onStoreChange) : () => {}),
		[store]
	);
	return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function createTokenUsageStore(): TokenUsageStore {
	return new TokenUsageStore();
}
