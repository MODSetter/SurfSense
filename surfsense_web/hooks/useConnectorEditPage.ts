import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast } from 'sonner';
import { useSearchSourceConnectors, SearchSourceConnector } from '@/hooks/useSearchSourceConnectors';
import { 
    GithubRepo, 
    EditMode, 
    githubPatSchema, 
    editConnectorSchema, 
    GithubPatFormValues, 
    EditConnectorFormValues 
} from '@/components/editConnector/types';

// Define SlackChannelInfo interface as it might not be globally available
export interface SlackChannelInfo {
    id: string;
    name: string;
    is_private: boolean;
    is_member: boolean;
}

export function useConnectorEditPage(connectorId: number, searchSpaceId: string) {
    const router = useRouter();
    const { connectors, updateConnector, isLoading: connectorsLoading } = useSearchSourceConnectors();

    // State managed by the hook
    const [connector, setConnector] = useState<SearchSourceConnector | null>(null);
    const [originalConfig, setOriginalConfig] = useState<Record<string, any> | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const [currentSelectedRepos, setCurrentSelectedRepos] = useState<string[]>([]);
    const [originalPat, setOriginalPat] = useState<string>("");
    const [editMode, setEditMode] = useState<EditMode>('viewing');
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
            LINEAR_API_KEY: ""
        }, 
    });

    // Effect to load initial data
    useEffect(() => {
        if (!connectorsLoading && connectors.length > 0 && !connector) {
            const currentConnector = connectors.find(c => c.id === connectorId);
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
                    LINEAR_API_KEY: config.LINEAR_API_KEY || "",
                    LINKUP_API_KEY: config.LINKUP_API_KEY || ""
                });
                if (currentConnector.connector_type === 'GITHUB_CONNECTOR') {
                    const savedRepos = config.repo_full_names || [];
                    const savedPat = config.GITHUB_PAT || "";
                    setCurrentSelectedRepos(savedRepos);
                    setNewSelectedRepos(savedRepos);
                    setOriginalPat(savedPat);
                    patForm.reset({ github_pat: savedPat });
                    setEditMode('viewing');
                }
            } else {
                toast.error("Connector not found.");
                router.push(`/dashboard/${searchSpaceId}/connectors`);
            }
        }
    }, [connectorId, connectors, connectorsLoading, router, searchSpaceId, connector, editForm, patForm]);

    // Handlers managed by the hook
    const handleFetchRepositories = useCallback(async (values: GithubPatFormValues) => {
        setIsFetchingRepos(true);
        setFetchedRepos(null);
        try {
            const token = localStorage.getItem('surfsense_bearer_token');
            if (!token) throw new Error('No auth token');
            const response = await fetch(
                `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/github/repositories/`,
                { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify({ github_pat: values.github_pat }) }
            );
            if (!response.ok) { const err = await response.json(); throw new Error(err.detail || 'Fetch failed'); }
            const data: GithubRepo[] = await response.json();
            setFetchedRepos(data);
            setNewSelectedRepos(currentSelectedRepos);
            toast.success(`Found ${data.length} repos.`);
        } catch (error) {
            console.error("Error fetching GitHub repositories:", error);
            toast.error(error instanceof Error ? error.message : "Failed to fetch repositories.");
        } finally { setIsFetchingRepos(false); }
    }, [currentSelectedRepos]); // Added dependency

    const handleRepoSelectionChange = useCallback((repoFullName: string, checked: boolean) => {
        setNewSelectedRepos(prev => checked ? [...prev, repoFullName] : prev.filter(name => name !== repoFullName));
    }, []);

    const handleSaveChanges = useCallback(async (formData: EditConnectorFormValues) => {
        if (!connector) {
            toast.error("Connector data not loaded.");
            setIsSaving(false);
            return;
        }
        // Ensure originalConfig is loaded, if not, it's an issue.
        if (!originalConfig && connector.connector_type !== 'GITHUB_CONNECTOR') { 
            // For GitHub, originalConfig might be less critical if PAT is the only config and handled by originalPat
            // but for others like Slack, it's needed for comparison.
            toast.error("Original configuration not available. Cannot determine changes.");
            setIsSaving(false);
            return;
        }

        setIsSaving(true);
        const updatePayload: Partial<SearchSourceConnector> = {};
        let configChanged = false;
        let newConfigForPayload: Record<string, any> | null = null;

        if (formData.name !== connector.name) {
            updatePayload.name = formData.name;
        }

        switch (connector.connector_type) {
            case 'GITHUB_CONNECTOR':
                const currentPatInForm = patForm.getValues('github_pat');
                const patChanged = currentPatInForm !== originalPat;
                const initialRepoSet = new Set(currentSelectedRepos);
                const newRepoSet = new Set(newSelectedRepos);
                const reposChanged = initialRepoSet.size !== newRepoSet.size || ![...initialRepoSet].every(repo => newRepoSet.has(repo));

                if (patChanged || (editMode === 'editing_repos' && reposChanged && fetchedRepos !== null)) {
                    if (!currentPatInForm || !(currentPatInForm.startsWith('ghp_') || currentPatInForm.startsWith('github_pat_'))) {
                        toast.error("Invalid GitHub PAT format. Cannot save.");
                        setIsSaving(false);
                        return;
                    }
                    newConfigForPayload = { GITHUB_PAT: currentPatInForm, repo_full_names: newSelectedRepos };
                    if (reposChanged && newSelectedRepos.length === 0) {
                        toast.warning("Warning: No repositories selected.");
                    }
                }
                break;
            case 'SLACK_CONNECTOR':
                const formDefinedSlackConfig = formData.config; // This now comes from editConnectorSchema
                // originalConfig should represent the whole config object for the connector
                if (formDefinedSlackConfig && JSON.stringify(formDefinedSlackConfig) !== JSON.stringify(originalConfig)) {
                    if (!formDefinedSlackConfig.SLACK_BOT_TOKEN || typeof formDefinedSlackConfig.SLACK_BOT_TOKEN !== 'string' || formDefinedSlackConfig.SLACK_BOT_TOKEN.trim() === '') {
                        toast.error("Slack Bot Token cannot be empty in config.");
                        setIsSaving(false);
                        return;
                    }
                    newConfigForPayload = { ...formDefinedSlackConfig };
                }
                break;
            case 'NOTION_CONNECTOR':
                // Assuming NOTION_INTEGRATION_TOKEN is directly on formData, not in formData.config
                // If it were moved to formData.config, this logic would need to mirror Slack's.
                if (formData.NOTION_INTEGRATION_TOKEN !== (originalConfig?.NOTION_INTEGRATION_TOKEN || "")) {
                    if (!formData.NOTION_INTEGRATION_TOKEN || formData.NOTION_INTEGRATION_TOKEN.trim() === '') {
                        toast.error("Notion Integration Token cannot be empty.");
                        setIsSaving(false);
                        return;
                    }
                    newConfigForPayload = { NOTION_INTEGRATION_TOKEN: formData.NOTION_INTEGRATION_TOKEN };
                }
                break;
            case 'SERPER_API':
                if (formData.SERPER_API_KEY !== (originalConfig?.SERPER_API_KEY || "")) {
                     if (!formData.SERPER_API_KEY || formData.SERPER_API_KEY.trim() === '') {
                        toast.error("Serper API Key cannot be empty.");
                        setIsSaving(false);
                        return;
                    }
                    newConfigForPayload = { SERPER_API_KEY: formData.SERPER_API_KEY };
                }
                break;
            case 'TAVILY_API':
                if (formData.TAVILY_API_KEY !== (originalConfig?.TAVILY_API_KEY || "")) {
                    if (!formData.TAVILY_API_KEY || formData.TAVILY_API_KEY.trim() === '') {
                        toast.error("Tavily API Key cannot be empty.");
                        setIsSaving(false);
                        return;
                    }
                    newConfigForPayload = { TAVILY_API_KEY: formData.TAVILY_API_KEY };
                }
                break;
            case 'LINEAR_CONNECTOR':
                if (formData.LINEAR_API_KEY !== (originalConfig?.LINEAR_API_KEY || "")) {
                    if (!formData.LINEAR_API_KEY || formData.LINEAR_API_KEY.trim() === '') {
                        toast.error("Linear API Key cannot be empty.");
                        setIsSaving(false);
                        return;
                    }
                    newConfigForPayload = { LINEAR_API_KEY: formData.LINEAR_API_KEY };
                }
                break;
            case 'LINKUP_API':
                 if (formData.LINKUP_API_KEY !== (originalConfig?.LINKUP_API_KEY || "")) {
                    if (!formData.LINKUP_API_KEY || formData.LINKUP_API_KEY.trim() === '') {
                        toast.error("Linkup API Key cannot be empty.");
                        setIsSaving(false);
                        return;
                    }
                    newConfigForPayload = { LINKUP_API_KEY: formData.LINKUP_API_KEY };
                }
                break;
            // Add other connector types if their config isn't simply a single token on formData
            // and needs to come from formData.config
        }

        if (newConfigForPayload !== null) {
            updatePayload.config = newConfigForPayload;
            configChanged = true; // Mark that config was changed
        }

        if (Object.keys(updatePayload).length === 0) {
            toast.info("No changes detected.");
            setIsSaving(false);
            if (connector.connector_type === 'GITHUB_CONNECTOR') {
                setEditMode('viewing');
                patForm.reset({ github_pat: originalPat });
            }
            return;
        }

        try {
            await updateConnector(connectorId, updatePayload);
            toast.success("Connector updated successfully!");

            const newActualSavedConfig = updatePayload.config || originalConfig || {};
            setOriginalConfig(newActualSavedConfig); // Update originalConfig to the new state

            // Update the connector state to reflect changes immediately in UI
            setConnector(prev => {
                if (!prev) return null;
                return {
                    ...prev,
                    name: updatePayload.name || prev.name,
                    config: newActualSavedConfig,
                };
            });
            
            // Reset form values to reflect saved state
            // For name
            if (updatePayload.name) {
                editForm.reset({ ...editForm.getValues(), name: updatePayload.name });
            }

            // For config fields, depending on connector type
            if (configChanged) {
                if (connector.connector_type === 'GITHUB_CONNECTOR') {
                    const savedGitHubConfig = newActualSavedConfig as { GITHUB_PAT?: string; repo_full_names?: string[] };
                    setCurrentSelectedRepos(savedGitHubConfig.repo_full_names || []);
                    setOriginalPat(savedGitHubConfig.GITHUB_PAT || "");
                    setNewSelectedRepos(savedGitHubConfig.repo_full_names || []); // Reset selection buffer
                    patForm.reset({ github_pat: savedGitHubConfig.GITHUB_PAT || "" });
                    setEditMode('viewing');
                    setFetchedRepos(null); // Clear fetched repos list
                } else if (connector.connector_type === 'SLACK_CONNECTOR') {
                    // EditSlackConnectorConfigForm relies on `connector.config` prop which is updated by setConnector
                    // and also on `editForm.setValue('config', ...)` if direct form manipulation is preferred.
                    // Let's ensure the form's 'config' field is also explicitly reset.
                    editForm.setValue('config', newActualSavedConfig);
                } else if (newActualSavedConfig.NOTION_INTEGRATION_TOKEN !== undefined) {
                    editForm.setValue('NOTION_INTEGRATION_TOKEN', newActualSavedConfig.NOTION_INTEGRATION_TOKEN || "");
                } else if (newActualSavedConfig.SERPER_API_KEY !== undefined) {
                    editForm.setValue('SERPER_API_KEY', newActualSavedConfig.SERPER_API_KEY || "");
                } else if (newActualSavedConfig.TAVILY_API_KEY !== undefined) {
                    editForm.setValue('TAVILY_API_KEY', newActualSavedConfig.TAVILY_API_KEY || "");
                } else if (newActualSavedConfig.LINEAR_API_KEY !== undefined) {
                    editForm.setValue('LINEAR_API_KEY', newActualSavedConfig.LINEAR_API_KEY || "");
                } else if (newActualSavedConfig.LINKUP_API_KEY !== undefined) {
                    editForm.setValue('LINKUP_API_KEY', newActualSavedConfig.LINKUP_API_KEY || "");
                }
            }
            
        } catch (error) {
            console.error("Error updating connector:", error);
            toast.error(error instanceof Error ? error.message : "Failed to update connector.");
        } finally {
            setIsSaving(false);
        }
    }, [
        connector, 
        originalConfig, // Ensure originalConfig is correctly representing the full config object for comparison
        updateConnector, 
        connectorId, 
        patForm, 
        originalPat, 
        currentSelectedRepos, 
        newSelectedRepos, 
        editMode, 
        fetchedRepos, 
        editForm, // Added editForm as it's used for setValue now
        // router, // router is not used directly in this function
        // searchSpaceId // not used directly
    ]);

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
        discoverSlackChannelsAPI, // Add the new function here
    };
}

// Implementation of discoverSlackChannelsAPI
async function discoverSlackChannelsAPI(connectorId: number): Promise<SlackChannelInfo[]> {
    const token = localStorage.getItem('surfsense_bearer_token');
    if (!token) {
        toast.error('Authentication token not found. Please log in again.');
        return [];
    }

    try {
        const response = await fetch(
            `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/slack/${connectorId}/discover-channels`,
            {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
            }
        );

        if (!response.ok) {
            let errorMsg = 'Failed to discover channels.';
            try {
                const errorData = await response.json();
                errorMsg = errorData.detail || errorMsg;
            } catch (e) {
                // Ignore if error response is not JSON
            }
            toast.error(`Failed to discover channels: ${errorMsg}`);
            return [];
        }

        const data = await response.json();
        if (data && Array.isArray(data.channels)) {
            // Optional: Add a success toast if needed, e.g.:
            // toast.success(`Discovered ${data.channels.length} channels.`);
            return data.channels as SlackChannelInfo[];
        } else {
            toast.error('Invalid response format from server when discovering channels.');
            return [];
        }
    } catch (error) {
        console.error("Error discovering Slack channels:", error);
        toast.error(error instanceof Error ? `Error discovering channels: ${error.message}` : "An unknown error occurred while discovering channels.");
        return [];
    }
}
