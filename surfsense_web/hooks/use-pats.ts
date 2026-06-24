"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type {
	CreatedPat,
	CreatePatRequest,
	PersonalAccessToken,
} from "@/contracts/types/pat.types";
import { patsApiService } from "@/lib/apis/pats-api.service";

export function usePats() {
	const [tokens, setTokens] = useState<PersonalAccessToken[]>([]);
	const [createdToken, setCreatedToken] = useState<CreatedPat | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [isMutating, setIsMutating] = useState(false);

	const refresh = useCallback(async () => {
		setIsLoading(true);
		try {
			const data = await patsApiService.listPats();
			setTokens(data);
		} catch (error) {
			console.error("Failed to load personal access tokens:", error);
			toast.error("Failed to load personal access tokens");
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const createToken = useCallback(
		async (request: CreatePatRequest) => {
			setIsMutating(true);
			try {
				const data = await patsApiService.createPat(request);
				setCreatedToken(data);
				await refresh();
				toast.success("Personal access token created");
				return data;
			} catch (error) {
				console.error("Failed to create personal access token:", error);
				toast.error("Failed to create personal access token");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const deleteToken = useCallback(
		async (id: number) => {
			setIsMutating(true);
			try {
				await patsApiService.deletePat(id);
				await refresh();
				toast.success("Personal access token deleted");
			} catch (error) {
				console.error("Failed to delete personal access token:", error);
				toast.error("Failed to delete personal access token");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	return {
		tokens,
		createdToken,
		setCreatedToken,
		isLoading,
		isMutating,
		refresh,
		createToken,
		deleteToken,
	};
}
