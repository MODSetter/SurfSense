"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

interface TokenHandlerProps {
	redirectPath?: string; // Path to redirect after storing token
	tokenParamName?: string; // Name of the URL parameter containing the token
	storageKey?: string; // Key to use when storing in localStorage
}

/**
 * Client component that extracts a token from URL parameters and stores it in localStorage
 *
 * @param redirectPath - Path to redirect after storing token (default: '/')
 * @param tokenParamName - Name of the URL parameter containing the token (default: 'token')
 * @param storageKey - Key to use when storing in localStorage (default: 'auth_token')
 */
const TokenHandler = ({
	redirectPath = "/",
	tokenParamName = "token",
	storageKey = "surfsense_bearer_token",
}: TokenHandlerProps) => {
	const router = useRouter();
	const searchParams = useSearchParams();

	useEffect(() => {
		// Only run on client-side
		if (typeof window === "undefined") return;

		// Get token from URL parameters
		const token = searchParams.get(tokenParamName);

		if (token) {
			try {
				// Store token in localStorage
				localStorage.setItem(storageKey, token);
				// console.log(`Token stored in localStorage with key: ${storageKey}`);

				// Redirect to specified path
				router.push(redirectPath);
			} catch (error) {
				console.error("Error storing token in localStorage:", error);
			}
		}
	}, [searchParams, tokenParamName, storageKey, redirectPath, router]);

	return (
		<div className="flex items-center justify-center min-h-[200px]">
			<p className="text-gray-500">Processing authentication...</p>
		</div>
	);
};

export default TokenHandler;
