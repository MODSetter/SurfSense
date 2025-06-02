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
            LINEAR_API_KEY: "",
            DISCORD_BOT_TOKEN: "",
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
                    LINKUP_API_KEY: config.LINKUP_API_KEY || "",
                    DISCORD_BOT_TOKEN: config.DISCORD_BOT_TOKEN || "",
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
        if (!connector || !originalConfig) return;
        setIsSaving(true);
        const updatePayload: Partial<SearchSourceConnector> = {};
        let configChanged = false;
        let newConfig: Record<string, any> | null = null;

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
                        toast.error("Invalid GitHub PAT format. Cannot save."); setIsSaving(false); return;
                    }
                    newConfig = { GITHUB_PAT: currentPatInForm, repo_full_names: newSelectedRepos };
                    if (reposChanged && newSelectedRepos.length === 0) { toast.warning("Warning: No repositories selected."); }
                }
                break;
            case 'SLACK_CONNECTOR':
                 if (formData.SLACK_BOT_TOKEN !== originalConfig.SLACK_BOT_TOKEN) {
                     if (!formData.SLACK_BOT_TOKEN) { toast.error("Slack Token empty."); setIsSaving(false); return; }
                     newConfig = { SLACK_BOT_TOKEN: formData.SLACK_BOT_TOKEN };
                 }
                 break;
             case 'NOTION_CONNECTOR':
                  if (formData.NOTION_INTEGRATION_TOKEN !== originalConfig.NOTION_INTEGRATION_TOKEN) {
                      if (!formData.NOTION_INTEGRATION_TOKEN) { toast.error("Notion Token empty."); setIsSaving(false); return; }
                      newConfig = { NOTION_INTEGRATION_TOKEN: formData.NOTION_INTEGRATION_TOKEN };
                  }
                  break;
               case 'SERPER_API':
                   if (formData.SERPER_API_KEY !== originalConfig.SERPER_API_KEY) {
                       if (!formData.SERPER_API_KEY) { toast.error("Serper Key empty."); setIsSaving(false); return; }
                       newConfig = { SERPER_API_KEY: formData.SERPER_API_KEY };
                   }
                   break;
               case 'TAVILY_API':
                   if (formData.TAVILY_API_KEY !== originalConfig.TAVILY_API_KEY) {
                       if (!formData.TAVILY_API_KEY) { toast.error("Tavily Key empty."); setIsSaving(false); return; }
                       newConfig = { TAVILY_API_KEY: formData.TAVILY_API_KEY };
                   }
                   break;
            
            case 'LINEAR_CONNECTOR':
                if (formData.LINEAR_API_KEY !== originalConfig.LINEAR_API_KEY) {
                    if (!formData.LINEAR_API_KEY) { 
                        toast.error("Linear API Key cannot be empty."); 
                        setIsSaving(false); 
                        return; 
                    }
                    newConfig = { LINEAR_API_KEY: formData.LINEAR_API_KEY };
                }
                break;
            case 'LINKUP_API':
                if (formData.LINKUP_API_KEY !== originalConfig.LINKUP_API_KEY) {
                    if (!formData.LINKUP_API_KEY) { toast.error("Linkup API Key cannot be empty."); setIsSaving(false); return; }
                    newConfig = { LINKUP_API_KEY: formData.LINKUP_API_KEY };
                }
                break;
            case 'DISCORD_CONNECTOR':
                if (formData.DISCORD_BOT_TOKEN !== originalConfig.DISCORD_BOT_TOKEN) {
                    if (!formData.DISCORD_BOT_TOKEN) { toast.error("Discord Bot Token cannot be empty."); setIsSaving(false); return; }
                    newConfig = { DISCORD_BOT_TOKEN: formData.DISCORD_BOT_TOKEN };
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
            if (connector.connector_type === 'GITHUB_CONNECTOR') { setEditMode('viewing'); patForm.reset({ github_pat: originalPat }); }
            return;
        }

        try {
            await updateConnector(connectorId, updatePayload);
            toast.success("Connector updated!");
            const newlySavedConfig = updatePayload.config || originalConfig;
            setOriginalConfig(newlySavedConfig);
            if (updatePayload.name) {
                 setConnector(prev => prev ? { ...prev, name: updatePayload.name!, config: newlySavedConfig } : null);
            }
            if (configChanged) {
                if (connector.connector_type === 'GITHUB_CONNECTOR') {
                     const savedGitHubConfig = newlySavedConfig as { GITHUB_PAT?: string; repo_full_names?: string[] };
                     setCurrentSelectedRepos(savedGitHubConfig.repo_full_names || []);
                     setOriginalPat(savedGitHubConfig.GITHUB_PAT || "");
                     setNewSelectedRepos(savedGitHubConfig.repo_full_names || []);
                     patForm.reset({ github_pat: savedGitHubConfig.GITHUB_PAT || "" });
                 } else if(connector.connector_type === 'SLACK_CONNECTOR') {
                    editForm.setValue('SLACK_BOT_TOKEN', newlySavedConfig.SLACK_BOT_TOKEN || "");
                 } else if(connector.connector_type === 'NOTION_CONNECTOR') {
                    editForm.setValue('NOTION_INTEGRATION_TOKEN', newlySavedConfig.NOTION_INTEGRATION_TOKEN || "");
                 } else if(connector.connector_type === 'SERPER_API') {
                    editForm.setValue('SERPER_API_KEY', newlySavedConfig.SERPER_API_KEY || "");
                 } else if(connector.connector_type === 'TAVILY_API') {
                    editForm.setValue('TAVILY_API_KEY', newlySavedConfig.TAVILY_API_KEY || "");
                 } else if(connector.connector_type === 'LINEAR_CONNECTOR') {
                    editForm.setValue('LINEAR_API_KEY', newlySavedConfig.LINEAR_API_KEY || "");
                 } else if(connector.connector_type === 'LINKUP_API') {
                    editForm.setValue('LINKUP_API_KEY', newlySavedConfig.LINKUP_API_KEY || "");
                 } else if(connector.connector_type === 'DISCORD_CONNECTOR') {
                    editForm.setValue('DISCORD_BOT_TOKEN', newlySavedConfig.DISCORD_BOT_TOKEN || "");
                 }
             }
            if (connector.connector_type === 'GITHUB_CONNECTOR') {
                 setEditMode('viewing');
                 setFetchedRepos(null);
             }
            // Resetting simple form values is handled by useEffect if connector state updates
        } catch (error) {
            console.error("Error updating connector:", error);
            toast.error(error instanceof Error ? error.message : "Failed to update connector.");
        } finally { setIsSaving(false); }
    }, [connector, originalConfig, updateConnector, connectorId, patForm, originalPat, currentSelectedRepos, newSelectedRepos, editMode, fetchedRepos, editForm]); // Added editForm to dependencies

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
