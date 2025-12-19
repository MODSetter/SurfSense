import { useEffect, useState } from "react";
import type { ResearchMode } from "@/components/chat";
import type { Document } from "@/contracts/types/document.types";
import { getBearerToken } from "@/lib/auth-utils";

interface UseChatStateProps {
	search_space_id: string;
	chat_id?: string;
}

export function useChatState({ chat_id }: UseChatStateProps) {
	const [token, setToken] = useState<string | null>(null);
	const [isLoading, setIsLoading] = useState(false);
	const [currentChatId, setCurrentChatId] = useState<string | null>(chat_id || null);

	// Chat configuration state
	const [researchMode, setResearchMode] = useState<ResearchMode>("QNA");
	const [selectedConnectors, setSelectedConnectors] = useState<string[]>([]);
	const [selectedDocuments, setSelectedDocuments] = useState<Document[]>([]);
	const [topK, setTopK] = useState<number>(5);

	useEffect(() => {
		const bearerToken = getBearerToken();
		setToken(bearerToken);
	}, []);

	return {
		token,
		setToken,
		isLoading,
		setIsLoading,
		currentChatId,
		setCurrentChatId,
		researchMode,
		setResearchMode,
		selectedConnectors,
		setSelectedConnectors,
		selectedDocuments,
		setSelectedDocuments,
		topK,
		setTopK,
	};
}
