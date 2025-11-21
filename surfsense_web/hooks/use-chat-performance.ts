"use client";

import { useCallback, useRef, useState } from "react";

export interface ChatPerformanceMetrics {
	/** Time to first byte/token in milliseconds */
	ttfb: number | null;
	/** Total response time in milliseconds */
	totalTime: number | null;
	/** Estimated tokens per second */
	tokensPerSecond: number | null;
	/** Total tokens generated (estimated from response length) */
	totalTokens: number | null;
	/** Model used for this response */
	model: string | null;
	/** Timestamp when request started */
	startTime: number | null;
	/** Whether streaming is currently active */
	isStreaming: boolean;
}

export interface PerformanceLog extends ChatPerformanceMetrics {
	/** Unique ID for this chat interaction */
	id: string;
	/** User's message */
	userMessage: string;
	/** Timestamp of the interaction */
	timestamp: number;
}

/**
 * Hook for tracking and measuring chat performance metrics
 * Tracks TTFB, response time, tokens/second, and provides logging
 */
export function useChatPerformance() {
	const [currentMetrics, setCurrentMetrics] = useState<ChatPerformanceMetrics>({
		ttfb: null,
		totalTime: null,
		tokensPerSecond: null,
		totalTokens: null,
		model: null,
		startTime: null,
		isStreaming: false,
	});

	const [performanceLog, setPerformanceLog] = useState<PerformanceLog[]>([]);

	// Refs to track timing without causing re-renders
	const startTimeRef = useRef<number | null>(null);
	const firstTokenTimeRef = useRef<number | null>(null);
	const tokenCountRef = useRef<number>(0);
	const currentMessageIdRef = useRef<string | null>(null);
	const currentUserMessageRef = useRef<string>("");
	const currentModelRef = useRef<string | null>(null);

	/**
	 * Start tracking performance for a new chat interaction
	 */
	const startTracking = useCallback((messageId: string, userMessage: string, model?: string) => {
		const now = performance.now();
		startTimeRef.current = now;
		firstTokenTimeRef.current = null;
		tokenCountRef.current = 0;
		currentMessageIdRef.current = messageId;
		currentUserMessageRef.current = userMessage;
		currentModelRef.current = model || null;

		setCurrentMetrics({
			ttfb: null,
			totalTime: null,
			tokensPerSecond: null,
			totalTokens: null,
			model: model || null,
			startTime: now,
			isStreaming: true,
		});
	}, []);

	/**
	 * Record when first token is received
	 */
	const recordFirstToken = useCallback(() => {
		if (firstTokenTimeRef.current === null && startTimeRef.current !== null) {
			const now = performance.now();
			firstTokenTimeRef.current = now;
			const ttfb = now - startTimeRef.current;

			setCurrentMetrics((prev) => ({
				...prev,
				ttfb,
			}));

			console.log(`[Chat Performance] TTFB: ${ttfb.toFixed(2)}ms`);
		}
	}, []);

	/**
	 * Record a token (or chunk of text)
	 * Estimates tokens based on text length (rough approximation: 4 chars = 1 token)
	 */
	const recordToken = useCallback((text: string) => {
		// Rough token estimation: ~4 characters per token
		const estimatedTokens = Math.ceil(text.length / 4);
		tokenCountRef.current += estimatedTokens;

		// Record first token timing if this is the first chunk
		if (firstTokenTimeRef.current === null) {
			recordFirstToken();
		}
	}, [recordFirstToken]);

	/**
	 * Complete tracking and calculate final metrics
	 */
	const completeTracking = useCallback(() => {
		if (startTimeRef.current === null) return;

		const now = performance.now();
		const totalTime = now - startTimeRef.current;
		const totalTokens = tokenCountRef.current;

		// Calculate tokens per second
		const tokensPerSecond = totalTime > 0 ? (totalTokens / totalTime) * 1000 : null;

		const finalMetrics: ChatPerformanceMetrics = {
			ttfb: firstTokenTimeRef.current
				? firstTokenTimeRef.current - startTimeRef.current
				: null,
			totalTime,
			tokensPerSecond,
			totalTokens,
			model: currentModelRef.current,
			startTime: startTimeRef.current,
			isStreaming: false,
		};

		setCurrentMetrics(finalMetrics);

		// Log to performance history
		if (currentMessageIdRef.current) {
			const logEntry: PerformanceLog = {
				...finalMetrics,
				id: currentMessageIdRef.current,
				userMessage: currentUserMessageRef.current,
				timestamp: Date.now(),
			};

			setPerformanceLog((prev) => [...prev.slice(-49), logEntry]); // Keep last 50 entries

			// Console log for debugging
			console.log(`[Chat Performance] Completed:`, {
				ttfb: finalMetrics.ttfb ? `${finalMetrics.ttfb.toFixed(2)}ms` : "N/A",
				totalTime: finalMetrics.totalTime !== null ? `${finalMetrics.totalTime.toFixed(2)}ms` : "N/A",
				tokensPerSecond: finalMetrics.tokensPerSecond
					? `${finalMetrics.tokensPerSecond.toFixed(2)} tokens/s`
					: "N/A",
				totalTokens: finalMetrics.totalTokens,
				model: finalMetrics.model,
			});
		}
	}, []);

	/**
	 * Reset tracking (useful for errors or cancellations)
	 */
	const resetTracking = useCallback(() => {
		startTimeRef.current = null;
		firstTokenTimeRef.current = null;
		tokenCountRef.current = 0;
		currentMessageIdRef.current = null;
		currentUserMessageRef.current = "";
		currentModelRef.current = null;

		setCurrentMetrics({
			ttfb: null,
			totalTime: null,
			tokensPerSecond: null,
			totalTokens: null,
			model: null,
			startTime: null,
			isStreaming: false,
		});
	}, []);

	/**
	 * Get average metrics from recent performance logs
	 */
	const getAverageMetrics = useCallback(() => {
		if (performanceLog.length === 0) return null;

		const validLogs = performanceLog.filter(
			(log) => log.ttfb !== null && log.totalTime !== null && log.tokensPerSecond !== null
		);

		if (validLogs.length === 0) return null;

		const sum = validLogs.reduce(
			(acc, log) => ({
				ttfb: acc.ttfb + (log.ttfb || 0),
				totalTime: acc.totalTime + (log.totalTime || 0),
				tokensPerSecond: acc.tokensPerSecond + (log.tokensPerSecond || 0),
			}),
			{ ttfb: 0, totalTime: 0, tokensPerSecond: 0 }
		);

		return {
			avgTtfb: sum.ttfb / validLogs.length,
			avgTotalTime: sum.totalTime / validLogs.length,
			avgTokensPerSecond: sum.tokensPerSecond / validLogs.length,
			sampleSize: validLogs.length,
		};
	}, [performanceLog]);

	return {
		currentMetrics,
		performanceLog,
		startTracking,
		recordFirstToken,
		recordToken,
		completeTracking,
		resetTracking,
		getAverageMetrics,
	};
}
