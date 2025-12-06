import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { getBearerToken } from "@/lib/auth-utils";

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

	const fallbackCopyTextToClipboard = (text: string) => {
		const textArea = document.createElement("textarea");
		textArea.value = text;

		// Avoid scrolling to bottom
		textArea.style.top = "0";
		textArea.style.left = "0";
		textArea.style.position = "fixed";
		textArea.style.opacity = "0";

		document.body.appendChild(textArea);
		textArea.focus();
		textArea.select();

		try {
			const successful = document.execCommand("copy");
			document.body.removeChild(textArea);

			if (successful) {
				setCopied(true);
				toast.success("API key copied to clipboard");

				setTimeout(() => {
					setCopied(false);
				}, 2000);
			} else {
				toast.error("Failed to copy API key");
			}
		} catch (err) {
			console.error("Fallback: Oops, unable to copy", err);
			document.body.removeChild(textArea);
			toast.error("Failed to copy API key");
		}
	};

	const copyToClipboard = useCallback(async () => {
		if (!apiKey) return;

		try {
			if (navigator.clipboard && window.isSecureContext) {
				// Use Clipboard API if available and in secure context
				await navigator.clipboard.writeText(apiKey);
				setCopied(true);
				toast.success("API key copied to clipboard");

				setTimeout(() => {
					setCopied(false);
				}, 2000);
			} else {
				// Fallback for non-secure contexts or browsers without clipboard API
				fallbackCopyTextToClipboard(apiKey);
			}
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
