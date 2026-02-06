import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { getBearerToken } from "@/lib/auth-utils";
import { copyToClipboard as copyToClipboardUtil } from "@/lib/utils";

interface UseApiKeyReturn {
	apiKey: string | null;
	isLoading: boolean;
	copied: boolean;
	copyToClipboard: () => Promise<void>;
}

export function useApiKey(): UseApiKeyReturn {
	const [apiKey, setApiKey] = useState<string | null>(null);
	const [copied, setCopied] = useState(false);
	const [isLoading, setIsLoading] = useState(true);

	useEffect(() => {
		// Load API key from localStorage
		const loadApiKey = () => {
			try {
				const token = getBearerToken();
				setApiKey(token);
			} catch (error) {
				console.error("Error loading API key:", error);
				toast.error("Failed to load API key");
			} finally {
				setIsLoading(false);
			}
		};

		// Add a small delay to simulate loading
		const timer = setTimeout(loadApiKey, 500);
		return () => clearTimeout(timer);
	}, []);

	const copyToClipboard = useCallback(async () => {
		if (!apiKey) return;

		const success = await copyToClipboardUtil(apiKey);
		if (success) {
			setCopied(true);
			toast.success("API key copied to clipboard");
			setTimeout(() => {
				setCopied(false);
			}, 2000);
		} else {
			toast.error("Failed to copy API key");
		}
	}, [apiKey]);

	return {
		apiKey,
		isLoading,
		copied,
		copyToClipboard,
	};
}
