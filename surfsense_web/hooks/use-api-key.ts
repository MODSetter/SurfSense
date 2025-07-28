import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

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
				const token = localStorage.getItem("surfsense_bearer_token");
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

		try {
			await navigator.clipboard.writeText(apiKey);
			setCopied(true);
			toast.success("API key copied to clipboard");

			setTimeout(() => {
				setCopied(false);
			}, 2000);
		} catch (err) {
			console.error("Failed to copy:", err);
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
