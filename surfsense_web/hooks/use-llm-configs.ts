"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";

export interface LLMConfig {
	id: number;
	name: string;
	provider: string;
	custom_provider?: string;
	model_name: string;
	api_key: string;
	api_base?: string;
	language?: string;
	litellm_params?: Record<string, any>;
	created_at: string;
	search_space_id: number;
}

export interface LLMPreferences {
	long_context_llm_id?: number;
	fast_llm_id?: number;
	strategic_llm_id?: number;
	long_context_llm?: LLMConfig;
	fast_llm?: LLMConfig;
	strategic_llm?: LLMConfig;
}

export interface CreateLLMConfig {
	name: string;
	provider: string;
	custom_provider?: string;
	model_name: string;
	api_key: string;
	api_base?: string;
	language?: string;
	litellm_params?: Record<string, any>;
	search_space_id: number;
}

export interface UpdateLLMConfig {
	name?: string;
	provider?: string;
	custom_provider?: string;
	model_name?: string;
	api_key?: string;
	api_base?: string;
	litellm_params?: Record<string, any>;
}

export function useLLMConfigs(searchSpaceId: number | null) {
	const [llmConfigs, setLlmConfigs] = useState<LLMConfig[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchLLMConfigs = async () => {
		if (!searchSpaceId) {
			setLoading(false);
			return;
		}

		try {
			setLoading(true);
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/llm-configs?search_space_id=${searchSpaceId}`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (!response.ok) {
				throw new Error("Failed to fetch LLM configurations");
			}

			const data = await response.json();
			setLlmConfigs(data);
			setError(null);
		} catch (err: any) {
			setError(err.message || "Failed to fetch LLM configurations");
			console.error("Error fetching LLM configurations:", err);
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		fetchLLMConfigs();
	}, [searchSpaceId]);

	const createLLMConfig = async (config: CreateLLMConfig): Promise<LLMConfig | null> => {
		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/llm-configs`,
				{
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					body: JSON.stringify(config),
				}
			);

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || "Failed to create LLM configuration");
			}

			const newConfig = await response.json();
			setLlmConfigs((prev) => [...prev, newConfig]);
			toast.success("LLM configuration created successfully");
			return newConfig;
		} catch (err: any) {
			toast.error(err.message || "Failed to create LLM configuration");
			console.error("Error creating LLM configuration:", err);
			return null;
		}
	};

	const deleteLLMConfig = async (id: number): Promise<boolean> => {
		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/llm-configs/${id}`,
				{
					method: "DELETE",
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
				}
			);

			if (!response.ok) {
				throw new Error("Failed to delete LLM configuration");
			}

			setLlmConfigs((prev) => prev.filter((config) => config.id !== id));
			toast.success("LLM configuration deleted successfully");
			return true;
		} catch (err: any) {
			toast.error(err.message || "Failed to delete LLM configuration");
			console.error("Error deleting LLM configuration:", err);
			return false;
		}
	};

	const updateLLMConfig = async (
		id: number,
		config: UpdateLLMConfig
	): Promise<LLMConfig | null> => {
		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/llm-configs/${id}`,
				{
					method: "PUT",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					body: JSON.stringify(config),
				}
			);

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || "Failed to update LLM configuration");
			}

			const updatedConfig = await response.json();
			setLlmConfigs((prev) => prev.map((c) => (c.id === id ? updatedConfig : c)));
			toast.success("LLM configuration updated successfully");
			return updatedConfig;
		} catch (err: any) {
			toast.error(err.message || "Failed to update LLM configuration");
			console.error("Error updating LLM configuration:", err);
			return null;
		}
	};

	return {
		llmConfigs,
		loading,
		error,
		createLLMConfig,
		updateLLMConfig,
		deleteLLMConfig,
		refreshConfigs: fetchLLMConfigs,
	};
}

export function useLLMPreferences(searchSpaceId: number | null) {
	const [preferences, setPreferences] = useState<LLMPreferences>({});
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const fetchPreferences = async () => {
		if (!searchSpaceId) {
			setLoading(false);
			return;
		}

		try {
			setLoading(true);
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/llm-preferences`,
				{
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					method: "GET",
				}
			);

			if (!response.ok) {
				throw new Error("Failed to fetch LLM preferences");
			}

			const data = await response.json();
			setPreferences(data);
			setError(null);
		} catch (err: any) {
			setError(err.message || "Failed to fetch LLM preferences");
			console.error("Error fetching LLM preferences:", err);
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		fetchPreferences();
	}, [searchSpaceId]);

	const updatePreferences = async (newPreferences: Partial<LLMPreferences>): Promise<boolean> => {
		if (!searchSpaceId) {
			toast.error("Search space ID is required");
			return false;
		}

		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/llm-preferences`,
				{
					method: "PUT",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
					body: JSON.stringify(newPreferences),
				}
			);

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || "Failed to update LLM preferences");
			}

			const updatedPreferences = await response.json();
			setPreferences(updatedPreferences);
			toast.success("LLM preferences updated successfully");
			return true;
		} catch (err: any) {
			toast.error(err.message || "Failed to update LLM preferences");
			console.error("Error updating LLM preferences:", err);
			return false;
		}
	};

	const isOnboardingComplete = (): boolean => {
		return !!(
			preferences.long_context_llm_id &&
			preferences.fast_llm_id &&
			preferences.strategic_llm_id
		);
	};

	return {
		preferences,
		loading,
		error,
		updatePreferences,
		refreshPreferences: fetchPreferences,
		isOnboardingComplete,
	};
}
