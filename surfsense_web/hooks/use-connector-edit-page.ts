import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import {
	type EditConnectorFormValues,
	type EditMode,
	editConnectorSchema,
	type GithubPatFormValues,
	type GithubRepo,
	githubPatSchema,
} from "@/components/editConnector/types";
import {
	type SearchSourceConnector,
	useSearchSourceConnectors,
} from "@/hooks/use-search-source-connectors";

const normalizeListInput = (value: unknown): string[] => {
	if (Array.isArray(value)) {
		return value.map((item) => String(item).trim()).filter((item) => item.length > 0);
	}
	if (typeof value === "string") {
		return value
			.split(",")
			.map((item) => item.trim())
			.filter((item) => item.length > 0);
	}
	return [];
};

const arraysEqual = (a: string[], b: string[]): boolean => {
	if (a.length !== b.length) return false;
	return a.every((value, index) => value === b[index]);
};

const normalizeBoolean = (value: unknown): boolean | null => {
	if (typeof value === "boolean") return value;
	if (typeof value === "string") {
		const lowered = value.trim().toLowerCase();
		if (["true", "1", "yes", "on"].includes(lowered)) return true;
		if (["false", "0", "no", "off"].includes(lowered)) return false;
	}
	if (typeof value === "number") {
		if (value === 1) return true;
		if (value === 0) return false;
	}
	return null;
};

export function useConnectorEditPage(connectorId: number, searchSpaceId: string) {
	const router = useRouter();
	const {
		connectors,
		updateConnector,
		isLoading: connectorsLoading,
	} = useSearchSourceConnectors(false, parseInt(searchSpaceId));

	// State managed by the hook
	const [connector, setConnector] = useState<SearchSourceConnector | null>(null);
	const [originalConfig, setOriginalConfig] = useState<Record<string, any> | null>(null);
	const [isSaving, setIsSaving] = useState(false);
	const [currentSelectedRepos, setCurrentSelectedRepos] = useState<string[]>([]);
	const [originalPat, setOriginalPat] = useState<string>("");
	const [editMode, setEditMode] = useState<EditMode>("viewing");
	const [fetchedRepos, setFetchedRepos] = useState<GithubRepo[] | null>(null);
	const [newSelectedRepos, setNewSelectedRepos] = useState<string[]>([]);
	const [isFetchingRepos, setIsFetchingRepos] = useState(false);

	// Forms managed by the hook
	const patForm = useForm<GithubPatFormValues>({
		resolver: zodResolver(githubPatSchema),
		defaultValues: { github_pat: "" },
	});
	const editForm = useForm<EditConnectorFormValues>({
		resolver: zodResolver(editConnectorSchema),
		defaultValues: {
			name: "",
			SLACK_BOT_TOKEN: "",
			NOTION_INTEGRATION_TOKEN: "",
			SERPER_API_KEY: "",
			TAVILY_API_KEY: "",
			SEARXNG_HOST: "",
			SEARXNG_API_KEY: "",
			SEARXNG_ENGINES: "",
			SEARXNG_CATEGORIES: "",
			SEARXNG_LANGUAGE: "",
			SEARXNG_SAFESEARCH: "",
			SEARXNG_VERIFY_SSL: "",
			LINEAR_API_KEY: "",
			DISCORD_BOT_TOKEN: "",
			CONFLUENCE_BASE_URL: "",
			CONFLUENCE_EMAIL: "",
			CONFLUENCE_API_TOKEN: "",
			JIRA_BASE_URL: "",
			JIRA_EMAIL: "",
			JIRA_API_TOKEN: "",
			LUMA_API_KEY: "",
			ELASTICSEARCH_API_KEY: "",
		},
	});

	// Effect to load initial data
	useEffect(() => {
		if (!connectorsLoading && connectors.length > 0 && !connector) {
			const currentConnector = connectors.find((c) => c.id === connectorId);
			if (currentConnector) {
				setConnector(currentConnector);
				const config = currentConnector.config || {};
				setOriginalConfig(config);
				editForm.reset({
					name: currentConnector.name,
					SLACK_BOT_TOKEN: config.SLACK_BOT_TOKEN || "",
					NOTION_INTEGRATION_TOKEN: config.NOTION_INTEGRATION_TOKEN || "",
					SERPER_API_KEY: config.SERPER_API_KEY || "",
					TAVILY_API_KEY: config.TAVILY_API_KEY || "",
					SEARXNG_HOST: config.SEARXNG_HOST || "",
					SEARXNG_API_KEY: config.SEARXNG_API_KEY || "",
					SEARXNG_ENGINES: Array.isArray(config.SEARXNG_ENGINES)
						? config.SEARXNG_ENGINES.join(", ")
						: config.SEARXNG_ENGINES || "",
					SEARXNG_CATEGORIES: Array.isArray(config.SEARXNG_CATEGORIES)
						? config.SEARXNG_CATEGORIES.join(", ")
						: config.SEARXNG_CATEGORIES || "",
					SEARXNG_LANGUAGE: config.SEARXNG_LANGUAGE || "",
					SEARXNG_SAFESEARCH:
						config.SEARXNG_SAFESEARCH !== undefined && config.SEARXNG_SAFESEARCH !== null
							? String(config.SEARXNG_SAFESEARCH)
							: "",
					SEARXNG_VERIFY_SSL:
						config.SEARXNG_VERIFY_SSL !== undefined && config.SEARXNG_VERIFY_SSL !== null
							? String(config.SEARXNG_VERIFY_SSL)
							: "",
					LINEAR_API_KEY: config.LINEAR_API_KEY || "",
					LINKUP_API_KEY: config.LINKUP_API_KEY || "",
					DISCORD_BOT_TOKEN: config.DISCORD_BOT_TOKEN || "",
					CONFLUENCE_BASE_URL: config.CONFLUENCE_BASE_URL || "",
					CONFLUENCE_EMAIL: config.CONFLUENCE_EMAIL || "",
					CONFLUENCE_API_TOKEN: config.CONFLUENCE_API_TOKEN || "",
					JIRA_BASE_URL: config.JIRA_BASE_URL || "",
					JIRA_EMAIL: config.JIRA_EMAIL || "",
					JIRA_API_TOKEN: config.JIRA_API_TOKEN || "",
					LUMA_API_KEY: config.LUMA_API_KEY || "",
					ELASTICSEARCH_API_KEY: config.ELASTICSEARCH_API_KEY || "",
				});
				if (currentConnector.connector_type === "GITHUB_CONNECTOR") {
					const savedRepos = config.repo_full_names || [];
					const savedPat = config.GITHUB_PAT || "";
					setCurrentSelectedRepos(savedRepos);
					setNewSelectedRepos(savedRepos);
					setOriginalPat(savedPat);
					patForm.reset({ github_pat: savedPat });
					setEditMode("viewing");
				}
			} else {
				toast.error("Connector not found.");
				router.push(`/dashboard/${searchSpaceId}/connectors`);
			}
		}
	}, [
		connectorId,
		connectors,
		connectorsLoading,
		router,
		searchSpaceId,
		connector,
		editForm,
		patForm,
	]);

	// Handlers managed by the hook
	const handleFetchRepositories = useCallback(
		async (values: GithubPatFormValues) => {
			setIsFetchingRepos(true);
			setFetchedRepos(null);
			try {
				const token = localStorage.getItem("surfsense_bearer_token");
				if (!token) throw new Error("No auth token");
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/github/repositories`,
					{
						method: "POST",
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${token}`,
						},
						body: JSON.stringify({ github_pat: values.github_pat }),
					}
				);
				if (!response.ok) {
					const err = await response.json();
					throw new Error(err.detail || "Fetch failed");
				}
				const data: GithubRepo[] = await response.json();
				setFetchedRepos(data);
				setNewSelectedRepos(currentSelectedRepos);
				toast.success(`Found ${data.length} repos.`);
			} catch (error) {
				console.error("Error fetching GitHub repositories:", error);
				toast.error(error instanceof Error ? error.message : "Failed to fetch repositories.");
			} finally {
				setIsFetchingRepos(false);
			}
		},
		[currentSelectedRepos]
	); // Added dependency

	const handleRepoSelectionChange = useCallback((repoFullName: string, checked: boolean) => {
		setNewSelectedRepos((prev) =>
			checked ? [...prev, repoFullName] : prev.filter((name) => name !== repoFullName)
		);
	}, []);

	const handleSaveChanges = useCallback(
		async (formData: EditConnectorFormValues) => {
			if (!connector || !originalConfig) return;
			setIsSaving(true);
			const updatePayload: Partial<SearchSourceConnector> = {};
			let configChanged = false;
			let newConfig: Record<string, any> | null = null;

			if (formData.name !== connector.name) {
				updatePayload.name = formData.name;
			}

			switch (connector.connector_type) {
				case "GITHUB_CONNECTOR": {
					const currentPatInForm = patForm.getValues("github_pat");
					const patChanged = currentPatInForm !== originalPat;
					const initialRepoSet = new Set(currentSelectedRepos);
					const newRepoSet = new Set(newSelectedRepos);
					const reposChanged =
						initialRepoSet.size !== newRepoSet.size ||
						![...initialRepoSet].every((repo) => newRepoSet.has(repo));
					if (
						patChanged ||
						(editMode === "editing_repos" && reposChanged && fetchedRepos !== null)
					) {
						if (
							!currentPatInForm ||
							!(currentPatInForm.startsWith("ghp_") || currentPatInForm.startsWith("github_pat_"))
						) {
							toast.error("Invalid GitHub PAT format. Cannot save.");
							setIsSaving(false);
							return;
						}
						newConfig = {
							GITHUB_PAT: currentPatInForm,
							repo_full_names: newSelectedRepos,
						};
						if (reposChanged && newSelectedRepos.length === 0) {
							toast.warning("Warning: No repositories selected.");
						}
					}
					break;
				}
				case "SLACK_CONNECTOR":
					if (formData.SLACK_BOT_TOKEN !== originalConfig.SLACK_BOT_TOKEN) {
						if (!formData.SLACK_BOT_TOKEN) {
							toast.error("Slack Token empty.");
							setIsSaving(false);
							return;
						}
						newConfig = { SLACK_BOT_TOKEN: formData.SLACK_BOT_TOKEN };
					}
					break;
				case "NOTION_CONNECTOR":
					if (formData.NOTION_INTEGRATION_TOKEN !== originalConfig.NOTION_INTEGRATION_TOKEN) {
						if (!formData.NOTION_INTEGRATION_TOKEN) {
							toast.error("Notion Token empty.");
							setIsSaving(false);
							return;
						}
						newConfig = {
							NOTION_INTEGRATION_TOKEN: formData.NOTION_INTEGRATION_TOKEN,
						};
					}
					break;
				case "SERPER_API":
					if (formData.SERPER_API_KEY !== originalConfig.SERPER_API_KEY) {
						if (!formData.SERPER_API_KEY) {
							toast.error("Serper Key empty.");
							setIsSaving(false);
							return;
						}
						newConfig = { SERPER_API_KEY: formData.SERPER_API_KEY };
					}
					break;
				case "TAVILY_API":
					if (formData.TAVILY_API_KEY !== originalConfig.TAVILY_API_KEY) {
						if (!formData.TAVILY_API_KEY) {
							toast.error("Tavily Key empty.");
							setIsSaving(false);
							return;
						}
						newConfig = { TAVILY_API_KEY: formData.TAVILY_API_KEY };
					}
					break;
				case "SEARXNG_API": {
					const host = (formData.SEARXNG_HOST || "").trim();
					if (!host) {
						toast.error("SearxNG host is required.");
						setIsSaving(false);
						return;
					}

					const candidateConfig: Record<string, any> = { SEARXNG_HOST: host };
					let hasChanges = host !== (originalConfig.SEARXNG_HOST || "").trim();

					const apiKey = (formData.SEARXNG_API_KEY || "").trim();
					const originalApiKey = (originalConfig.SEARXNG_API_KEY || "").trim();
					if (apiKey !== originalApiKey) {
						candidateConfig.SEARXNG_API_KEY = apiKey || null;
						hasChanges = true;
					}

					const newEngines = normalizeListInput(formData.SEARXNG_ENGINES || "");
					const originalEngines = normalizeListInput(originalConfig.SEARXNG_ENGINES);
					if (!arraysEqual(newEngines, originalEngines)) {
						candidateConfig.SEARXNG_ENGINES = newEngines;
						hasChanges = true;
					}

					const newCategories = normalizeListInput(formData.SEARXNG_CATEGORIES || "");
					const originalCategories = normalizeListInput(originalConfig.SEARXNG_CATEGORIES);
					if (!arraysEqual(newCategories, originalCategories)) {
						candidateConfig.SEARXNG_CATEGORIES = newCategories;
						hasChanges = true;
					}

					const language = (formData.SEARXNG_LANGUAGE || "").trim();
					const originalLanguage = (originalConfig.SEARXNG_LANGUAGE || "").trim();
					if (language !== originalLanguage) {
						candidateConfig.SEARXNG_LANGUAGE = language || null;
						hasChanges = true;
					}

					const safesearchRaw = (formData.SEARXNG_SAFESEARCH || "").trim();
					const originalSafesearch = originalConfig.SEARXNG_SAFESEARCH;
					if (safesearchRaw) {
						const parsed = Number(safesearchRaw);
						if (Number.isNaN(parsed) || !Number.isInteger(parsed) || parsed < 0 || parsed > 2) {
							toast.error("SearxNG SafeSearch must be 0, 1, or 2.");
							setIsSaving(false);
							return;
						}
						if (parsed !== Number(originalSafesearch)) {
							candidateConfig.SEARXNG_SAFESEARCH = parsed;
							hasChanges = true;
						}
					} else if (originalSafesearch !== undefined && originalSafesearch !== null) {
						candidateConfig.SEARXNG_SAFESEARCH = null;
						hasChanges = true;
					}

					const verifyRaw = (formData.SEARXNG_VERIFY_SSL || "").trim().toLowerCase();
					const originalVerifyBool = normalizeBoolean(originalConfig.SEARXNG_VERIFY_SSL);
					if (verifyRaw) {
						let parsedBool: boolean | null = null;
						if (["true", "1", "yes", "on"].includes(verifyRaw)) parsedBool = true;
						else if (["false", "0", "no", "off"].includes(verifyRaw)) parsedBool = false;
						if (parsedBool === null) {
							toast.error("SearxNG SSL verification must be true or false.");
							setIsSaving(false);
							return;
						}
						if (parsedBool !== originalVerifyBool) {
							candidateConfig.SEARXNG_VERIFY_SSL = parsedBool;
							hasChanges = true;
						}
					} else if (originalVerifyBool !== null) {
						candidateConfig.SEARXNG_VERIFY_SSL = null;
						hasChanges = true;
					}

					if (hasChanges) {
						newConfig = candidateConfig;
					}
					break;
				}

				case "LINEAR_CONNECTOR":
					if (formData.LINEAR_API_KEY !== originalConfig.LINEAR_API_KEY) {
						if (!formData.LINEAR_API_KEY) {
							toast.error("Linear API Key cannot be empty.");
							setIsSaving(false);
							return;
						}
						newConfig = { LINEAR_API_KEY: formData.LINEAR_API_KEY };
					}
					break;
				case "LINKUP_API":
					if (formData.LINKUP_API_KEY !== originalConfig.LINKUP_API_KEY) {
						if (!formData.LINKUP_API_KEY) {
							toast.error("Linkup API Key cannot be empty.");
							setIsSaving(false);
							return;
						}
						newConfig = { LINKUP_API_KEY: formData.LINKUP_API_KEY };
					}
					break;
				case "DISCORD_CONNECTOR":
					if (formData.DISCORD_BOT_TOKEN !== originalConfig.DISCORD_BOT_TOKEN) {
						if (!formData.DISCORD_BOT_TOKEN) {
							toast.error("Discord Bot Token cannot be empty.");
							setIsSaving(false);
							return;
						}
						newConfig = { DISCORD_BOT_TOKEN: formData.DISCORD_BOT_TOKEN };
					}
					break;
				case "CONFLUENCE_CONNECTOR":
					if (
						formData.CONFLUENCE_BASE_URL !== originalConfig.CONFLUENCE_BASE_URL ||
						formData.CONFLUENCE_EMAIL !== originalConfig.CONFLUENCE_EMAIL ||
						formData.CONFLUENCE_API_TOKEN !== originalConfig.CONFLUENCE_API_TOKEN
					) {
						if (
							!formData.CONFLUENCE_BASE_URL ||
							!formData.CONFLUENCE_EMAIL ||
							!formData.CONFLUENCE_API_TOKEN
						) {
							toast.error("All Confluence fields are required.");
							setIsSaving(false);
							return;
						}
						newConfig = {
							CONFLUENCE_BASE_URL: formData.CONFLUENCE_BASE_URL,
							CONFLUENCE_EMAIL: formData.CONFLUENCE_EMAIL,
							CONFLUENCE_API_TOKEN: formData.CONFLUENCE_API_TOKEN,
						};
					}
					break;
				case "JIRA_CONNECTOR":
					if (
						formData.JIRA_BASE_URL !== originalConfig.JIRA_BASE_URL ||
						formData.JIRA_EMAIL !== originalConfig.JIRA_EMAIL ||
						formData.JIRA_API_TOKEN !== originalConfig.JIRA_API_TOKEN
					) {
						if (!formData.JIRA_BASE_URL || !formData.JIRA_EMAIL || !formData.JIRA_API_TOKEN) {
							toast.error("All Jira fields are required.");
							setIsSaving(false);
							return;
						}
						newConfig = {
							JIRA_BASE_URL: formData.JIRA_BASE_URL,
							JIRA_EMAIL: formData.JIRA_EMAIL,
							JIRA_API_TOKEN: formData.JIRA_API_TOKEN,
						};
					}
					break;
				case "LUMA_CONNECTOR":
					if (formData.LUMA_API_KEY !== originalConfig.LUMA_API_KEY) {
						if (!formData.LUMA_API_KEY) {
							toast.error("Luma API Key cannot be empty.");
							setIsSaving(false);
							return;
						}
						newConfig = { LUMA_API_KEY: formData.LUMA_API_KEY };
					}
					break;
				case "ELASTICSEARCH_CONNECTOR":
					if (formData.ELASTICSEARCH_API_KEY !== originalConfig.ELASTICSEARCH_API_KEY) {
						if (!formData.ELASTICSEARCH_API_KEY) {
							toast.error("Elasticsearch API Key cannot be empty.");
							setIsSaving(false);
							return;
						}
						newConfig = { ELASTICSEARCH_API_KEY: formData.ELASTICSEARCH_API_KEY };
					}
					break;
			}

			if (newConfig !== null) {
				updatePayload.config = newConfig;
				configChanged = true;
			}

			if (Object.keys(updatePayload).length === 0) {
				toast.info("No changes detected.");
				setIsSaving(false);
				if (connector.connector_type === "GITHUB_CONNECTOR") {
					setEditMode("viewing");
					patForm.reset({ github_pat: originalPat });
				}
				return;
			}

			try {
				await updateConnector(connectorId, updatePayload);
				toast.success("Connector updated!");
				const newlySavedConfig = updatePayload.config || originalConfig;
				setOriginalConfig(newlySavedConfig);
				if (updatePayload.name) {
					setConnector((prev) =>
						prev ? { ...prev, name: updatePayload.name!, config: newlySavedConfig } : null
					);
				}
				if (configChanged) {
					if (connector.connector_type === "GITHUB_CONNECTOR") {
						const savedGitHubConfig = newlySavedConfig as {
							GITHUB_PAT?: string;
							repo_full_names?: string[];
						};
						setCurrentSelectedRepos(savedGitHubConfig.repo_full_names || []);
						setOriginalPat(savedGitHubConfig.GITHUB_PAT || "");
						setNewSelectedRepos(savedGitHubConfig.repo_full_names || []);
						patForm.reset({ github_pat: savedGitHubConfig.GITHUB_PAT || "" });
					} else if (connector.connector_type === "SLACK_CONNECTOR") {
						editForm.setValue("SLACK_BOT_TOKEN", newlySavedConfig.SLACK_BOT_TOKEN || "");
					} else if (connector.connector_type === "NOTION_CONNECTOR") {
						editForm.setValue(
							"NOTION_INTEGRATION_TOKEN",
							newlySavedConfig.NOTION_INTEGRATION_TOKEN || ""
						);
					} else if (connector.connector_type === "SERPER_API") {
						editForm.setValue("SERPER_API_KEY", newlySavedConfig.SERPER_API_KEY || "");
					} else if (connector.connector_type === "TAVILY_API") {
						editForm.setValue("TAVILY_API_KEY", newlySavedConfig.TAVILY_API_KEY || "");
					} else if (connector.connector_type === "SEARXNG_API") {
						editForm.setValue("SEARXNG_HOST", newlySavedConfig.SEARXNG_HOST || "");
						editForm.setValue("SEARXNG_API_KEY", newlySavedConfig.SEARXNG_API_KEY || "");
						editForm.setValue(
							"SEARXNG_ENGINES",
							normalizeListInput(newlySavedConfig.SEARXNG_ENGINES).join(", ")
						);
						editForm.setValue(
							"SEARXNG_CATEGORIES",
							normalizeListInput(newlySavedConfig.SEARXNG_CATEGORIES).join(", ")
						);
						editForm.setValue("SEARXNG_LANGUAGE", newlySavedConfig.SEARXNG_LANGUAGE || "");
						editForm.setValue(
							"SEARXNG_SAFESEARCH",
							newlySavedConfig.SEARXNG_SAFESEARCH === null ||
								newlySavedConfig.SEARXNG_SAFESEARCH === undefined
								? ""
								: String(newlySavedConfig.SEARXNG_SAFESEARCH)
						);
						const verifyValue = normalizeBoolean(newlySavedConfig.SEARXNG_VERIFY_SSL);
						editForm.setValue(
							"SEARXNG_VERIFY_SSL",
							verifyValue === null ? "" : String(verifyValue)
						);
					} else if (connector.connector_type === "LINEAR_CONNECTOR") {
						editForm.setValue("LINEAR_API_KEY", newlySavedConfig.LINEAR_API_KEY || "");
					} else if (connector.connector_type === "LINKUP_API") {
						editForm.setValue("LINKUP_API_KEY", newlySavedConfig.LINKUP_API_KEY || "");
					} else if (connector.connector_type === "DISCORD_CONNECTOR") {
						editForm.setValue("DISCORD_BOT_TOKEN", newlySavedConfig.DISCORD_BOT_TOKEN || "");
					} else if (connector.connector_type === "CONFLUENCE_CONNECTOR") {
						editForm.setValue("CONFLUENCE_BASE_URL", newlySavedConfig.CONFLUENCE_BASE_URL || "");
						editForm.setValue("CONFLUENCE_EMAIL", newlySavedConfig.CONFLUENCE_EMAIL || "");
						editForm.setValue("CONFLUENCE_API_TOKEN", newlySavedConfig.CONFLUENCE_API_TOKEN || "");
					} else if (connector.connector_type === "JIRA_CONNECTOR") {
						editForm.setValue("JIRA_BASE_URL", newlySavedConfig.JIRA_BASE_URL || "");
						editForm.setValue("JIRA_EMAIL", newlySavedConfig.JIRA_EMAIL || "");
						editForm.setValue("JIRA_API_TOKEN", newlySavedConfig.JIRA_API_TOKEN || "");
					} else if (connector.connector_type === "LUMA_CONNECTOR") {
						editForm.setValue("LUMA_API_KEY", newlySavedConfig.LUMA_API_KEY || "");
					} else if (connector.connector_type === "ELASTICSEARCH_CONNECTOR") {
						editForm.setValue(
							"ELASTICSEARCH_API_KEY",
							newlySavedConfig.ELASTICSEARCH_API_KEY || ""
						);
					}
				}
				if (connector.connector_type === "GITHUB_CONNECTOR") {
					setEditMode("viewing");
					setFetchedRepos(null);
				}
				// Resetting simple form values is handled by useEffect if connector state updates
			} catch (error) {
				console.error("Error updating connector:", error);
				toast.error(error instanceof Error ? error.message : "Failed to update connector.");
			} finally {
				setIsSaving(false);
			}
		},
		[
			connector,
			originalConfig,
			updateConnector,
			connectorId,
			patForm,
			originalPat,
			currentSelectedRepos,
			newSelectedRepos,
			editMode,
			fetchedRepos,
			editForm,
		]
	); // Added editForm to dependencies

	// Return values needed by the component
	return {
		connectorsLoading,
		connector,
		isSaving,
		editForm,
		patForm,
		handleSaveChanges,
		// GitHub specific props
		editMode,
		setEditMode,
		originalPat,
		currentSelectedRepos,
		fetchedRepos,
		setFetchedRepos,
		newSelectedRepos,
		setNewSelectedRepos,
		isFetchingRepos,
		handleFetchRepositories,
		handleRepoSelectionChange,
	};
}
