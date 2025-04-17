"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { motion } from "framer-motion";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { toast } from "sonner";
import { ArrowLeft, Check, Info, Loader2, Github, CircleAlert, ListChecks, Edit, KeyRound } from "lucide-react";

import { useSearchSourceConnectors, SearchSourceConnector } from "@/hooks/useSearchSourceConnectors";
import {
    Form,
    FormControl,
    FormDescription,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Alert,
    AlertDescription,
    AlertTitle,
} from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";

// Helper function to get connector type display name (copied from manage page)
const getConnectorTypeDisplay = (type: string): string => {
    const typeMap: Record<string, string> = {
        "SERPER_API": "Serper API",
        "TAVILY_API": "Tavily API",
        "SLACK_CONNECTOR": "Slack",
        "NOTION_CONNECTOR": "Notion",
        "GITHUB_CONNECTOR": "GitHub",
    };
    return typeMap[type] || type;
};

// Schema for PAT input when editing GitHub repos (remains separate)
const githubPatSchema = z.object({
    github_pat: z.string()
        .min(20, { message: "GitHub Personal Access Token seems too short." })
        .refine(pat => pat.startsWith('ghp_') || pat.startsWith('github_pat_'), {
            message: "GitHub PAT should start with 'ghp_' or 'github_pat_'",
        }),
});
type GithubPatFormValues = z.infer<typeof githubPatSchema>;

// Updated schema for main edit form - includes optional fields for other connector configs
const editConnectorSchema = z.object({
    name: z.string().min(3, { message: "Connector name must be at least 3 characters." }),
    // Add optional fields for other connector types' configs
    SLACK_BOT_TOKEN: z.string().optional(),
    NOTION_INTEGRATION_TOKEN: z.string().optional(),
    SERPER_API_KEY: z.string().optional(),
    TAVILY_API_KEY: z.string().optional(),
    // GITHUB_PAT is handled separately via patForm for repo editing flow
});
type EditConnectorFormValues = z.infer<typeof editConnectorSchema>;

interface GithubRepo {
    id: number;
    name: string;
    full_name: string;
    private: boolean;
    url: string;
    description: string | null;
    last_updated: string | null;
}

type EditMode = 'viewing' | 'editing_repos'; // Only relevant for GitHub

export default function EditConnectorPage() { // Renamed for clarity
    const router = useRouter();
    const params = useParams();
    const searchSpaceId = params.search_space_id as string;
    const connectorId = parseInt(params.connector_id as string, 10);

    const { connectors, updateConnector, isLoading: connectorsLoading } = useSearchSourceConnectors();

    const [connector, setConnector] = useState<SearchSourceConnector | null>(null);
    const [originalConfig, setOriginalConfig] = useState<Record<string, any> | null>(null); // Store original config object

    // GitHub specific state (only used if connector type is GitHub)
    const [currentSelectedRepos, setCurrentSelectedRepos] = useState<string[]>([]);
    const [originalPat, setOriginalPat] = useState<string>("");
    const [editMode, setEditMode] = useState<EditMode>('viewing'); 
    const [fetchedRepos, setFetchedRepos] = useState<GithubRepo[] | null>(null);
    const [newSelectedRepos, setNewSelectedRepos] = useState<string[]>([]); 
    const [isFetchingRepos, setIsFetchingRepos] = useState(false);

    const [isSaving, setIsSaving] = useState(false);

    // Form for GitHub PAT input (only used for GitHub repo editing)
    const patForm = useForm<GithubPatFormValues>({
        resolver: zodResolver(githubPatSchema),
        defaultValues: { github_pat: "" },
    });

    // Main form for connector details (name + simple config fields)
    const editForm = useForm<EditConnectorFormValues>({
        resolver: zodResolver(editConnectorSchema),
        defaultValues: {
            name: "",
            SLACK_BOT_TOKEN: "",
            NOTION_INTEGRATION_TOKEN: "",
            SERPER_API_KEY: "",
            TAVILY_API_KEY: "",
        }, 
    });

    // Effect to load connector data
    useEffect(() => {
        if (!connectorsLoading && connectors.length > 0 && !connector) { 
            const currentConnector = connectors.find(c => c.id === connectorId);
            if (currentConnector) {
                setConnector(currentConnector);
                setOriginalConfig(currentConnector.config || {}); // Store original config

                // Reset main form with common and type-specific fields
                editForm.reset({
                    name: currentConnector.name,
                    SLACK_BOT_TOKEN: currentConnector.config?.SLACK_BOT_TOKEN || "",
                    NOTION_INTEGRATION_TOKEN: currentConnector.config?.NOTION_INTEGRATION_TOKEN || "",
                    SERPER_API_KEY: currentConnector.config?.SERPER_API_KEY || "",
                    TAVILY_API_KEY: currentConnector.config?.TAVILY_API_KEY || "",
                });

                // If GitHub, set up GitHub-specific state
                if (currentConnector.connector_type === 'GITHUB_CONNECTOR') {
                    const savedRepos = currentConnector.config?.repo_full_names || [];
                    const savedPat = currentConnector.config?.GITHUB_PAT || "";
                    setCurrentSelectedRepos(savedRepos);
                    setNewSelectedRepos(savedRepos); 
                    setOriginalPat(savedPat);
                    patForm.reset({ github_pat: savedPat });
                    setEditMode('viewing'); // Start in viewing mode for repos
                }
            } else {
                toast.error("Connector not found.");
                router.push(`/dashboard/${searchSpaceId}/connectors`);
            }
        }
    }, [connectorId, connectors, connectorsLoading, router, searchSpaceId, connector, editForm, patForm]); 

    // Fetch repositories using the entered PAT
    const handleFetchRepositories = async (values: GithubPatFormValues) => {
        setIsFetchingRepos(true);
        setFetchedRepos(null);
        try {
            const token = localStorage.getItem('surfsense_bearer_token');
            if (!token) throw new Error('No authentication token found');

            const response = await fetch(
                `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/github/repositories/`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ github_pat: values.github_pat })
                }
            );
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Failed to fetch repositories: ${response.statusText}`);
            }
            const data: GithubRepo[] = await response.json();
            setFetchedRepos(data);
            setNewSelectedRepos(currentSelectedRepos); 
            toast.success(`Found ${data.length} repositories. Select which ones to index.`);
        } catch (error) {
            console.error("Error fetching GitHub repositories:", error);
            toast.error(error instanceof Error ? error.message : "Failed to fetch repositories.");
        } finally {
            setIsFetchingRepos(false);
        }
    };

    // Handle checkbox changes during editing
    const handleRepoSelectionChange = (repoFullName: string, checked: boolean) => {
        setNewSelectedRepos(prev =>
            checked
                ? [...prev, repoFullName]
                : prev.filter(name => name !== repoFullName)
        );
    };

    // Save changes - updated to handle different connector types
    const handleSaveChanges = async (formData: EditConnectorFormValues) => {
        if (!connector || !originalConfig) return;

        setIsSaving(true);
        const updatePayload: Partial<SearchSourceConnector> = {};
        let configChanged = false;
        let newConfig: Record<string, any> | null = null;

        // 1. Check if name changed
        if (formData.name !== connector.name) {
            updatePayload.name = formData.name;
        }

        // 2. Check for config changes based on connector type
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
                        setIsSaving(false); return;
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

            case 'SLACK_CONNECTOR':
                if (formData.SLACK_BOT_TOKEN !== originalConfig.SLACK_BOT_TOKEN) {
                    if (!formData.SLACK_BOT_TOKEN) {
                        toast.error("Slack Bot Token cannot be empty."); setIsSaving(false); return;
                    }
                    newConfig = { SLACK_BOT_TOKEN: formData.SLACK_BOT_TOKEN };
                }
                break;

            case 'NOTION_CONNECTOR':
                if (formData.NOTION_INTEGRATION_TOKEN !== originalConfig.NOTION_INTEGRATION_TOKEN) {
                    if (!formData.NOTION_INTEGRATION_TOKEN) {
                        toast.error("Notion Integration Token cannot be empty."); setIsSaving(false); return;
                    }
                    newConfig = { NOTION_INTEGRATION_TOKEN: formData.NOTION_INTEGRATION_TOKEN };
                }
                break;

            case 'SERPER_API':
                if (formData.SERPER_API_KEY !== originalConfig.SERPER_API_KEY) {
                    if (!formData.SERPER_API_KEY) {
                        toast.error("Serper API Key cannot be empty."); setIsSaving(false); return;
                    }
                    newConfig = { SERPER_API_KEY: formData.SERPER_API_KEY };
                }
                break;

            case 'TAVILY_API':
                if (formData.TAVILY_API_KEY !== originalConfig.TAVILY_API_KEY) {
                    if (!formData.TAVILY_API_KEY) {
                        toast.error("Tavily API Key cannot be empty."); setIsSaving(false); return;
                    }
                    newConfig = { TAVILY_API_KEY: formData.TAVILY_API_KEY };
                }
                break;

            // Add cases for other connector types if necessary
        }

        // If config was determined to have changed, add it to the payload
        if (newConfig !== null) {
            updatePayload.config = newConfig;
            configChanged = true;
        }

        // 3. Check if there are actual changes to save
        if (Object.keys(updatePayload).length === 0) {
            toast.info("No changes detected.");
            setIsSaving(false);
            if (connector.connector_type === 'GITHUB_CONNECTOR') {
                setEditMode('viewing'); 
                patForm.reset({ github_pat: originalPat });
            }
            return;
        }

        // 4. Proceed with update API call
        try {
            await updateConnector(connectorId, updatePayload);
            toast.success("Connector updated successfully!");

            // Update local state after successful save
            const newlySavedConfig = updatePayload.config || originalConfig;
            setOriginalConfig(newlySavedConfig);
            if (updatePayload.name) {
                setConnector(prev => prev ? { ...prev, name: updatePayload.name!, config: newlySavedConfig } : null);
                editForm.setValue('name', updatePayload.name);
            } else {
                setConnector(prev => prev ? { ...prev, config: newlySavedConfig } : null);
            }

            if (connector.connector_type === 'GITHUB_CONNECTOR' && configChanged) {
                const savedGitHubConfig = newlySavedConfig as { GITHUB_PAT?: string; repo_full_names?: string[] };
                setCurrentSelectedRepos(savedGitHubConfig.repo_full_names || []);
                setOriginalPat(savedGitHubConfig.GITHUB_PAT || "");
                setNewSelectedRepos(savedGitHubConfig.repo_full_names || []);
                patForm.reset({ github_pat: savedGitHubConfig.GITHUB_PAT || "" });
            } else if (connector.connector_type === 'SLACK_CONNECTOR' && configChanged) {
                editForm.setValue('SLACK_BOT_TOKEN', newlySavedConfig.SLACK_BOT_TOKEN || "");
            } // Add similar blocks for Notion, Serper, Tavily
            else if (connector.connector_type === 'NOTION_CONNECTOR' && configChanged) {
                editForm.setValue('NOTION_INTEGRATION_TOKEN', newlySavedConfig.NOTION_INTEGRATION_TOKEN || "");
            } else if (connector.connector_type === 'SERPER_API' && configChanged) {
                editForm.setValue('SERPER_API_KEY', newlySavedConfig.SERPER_API_KEY || "");
            } else if (connector.connector_type === 'TAVILY_API' && configChanged) {
                editForm.setValue('TAVILY_API_KEY', newlySavedConfig.TAVILY_API_KEY || "");
            }

            // Reset GitHub specific edit state
            if (connector.connector_type === 'GITHUB_CONNECTOR') {
                setEditMode('viewing');
                setFetchedRepos(null);
            }

        } catch (error) {
            console.error("Error updating connector:", error);
            toast.error(error instanceof Error ? error.message : "Failed to update connector.");
        } finally {
            setIsSaving(false);
        }
    };

    if (connectorsLoading || !connector) {
        return (
            <div className="container mx-auto py-8 max-w-3xl">
                <Skeleton className="h-8 w-48 mb-6" />
                <Card className="border-2 border-border">
                    <CardHeader>
                        <Skeleton className="h-7 w-3/4 mb-2" />
                        <Skeleton className="h-4 w-full" />
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Skeleton className="h-10 w-full" />
                        <Skeleton className="h-20 w-full" />
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="container mx-auto py-8 max-w-3xl">
            <Button
                variant="ghost"
                className="mb-6"
                onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors`)}
            >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Connectors
            </Button>

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
            >
                <Card className="border-2 border-border">
                    <CardHeader>
                        {/* Title can be dynamic based on type */}
                        <CardTitle className="text-2xl font-bold flex items-center gap-2">
                            <Github className="h-6 w-6" /> {/* TODO: Make icon dynamic */}
                            Edit {getConnectorTypeDisplay(connector.connector_type)} Connector
                        </CardTitle>
                        <CardDescription>
                            Modify the connector name and configuration.
                        </CardDescription>
                    </CardHeader>

                    <Form {...editForm}>
                        <form onSubmit={editForm.handleSubmit(handleSaveChanges)} className="space-y-6">
                            <CardContent className="space-y-6">
                                {/* Name Field (Common) */}
                                <FormField
                                    control={editForm.control}
                                    name="name"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Connector Name</FormLabel>
                                            <FormControl><Input {...field} /></FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <hr />

                                {/* --- Conditional Configuration Section --- */}
                                <h3 className="text-lg font-semibold">Configuration</h3>

                                {/* == GitHub == */}
                                {connector.connector_type === 'GITHUB_CONNECTOR' && (
                                    <div className="space-y-4">
                                        <h4 className="font-medium text-muted-foreground">Repository Selection & Access</h4>
                                        {editMode === 'viewing' && (
                                            <div className="space-y-3 p-4 border rounded-md bg-muted/50">
                                                <FormLabel>Currently Indexed Repositories:</FormLabel>
                                                {currentSelectedRepos.length > 0 ? (
                                                    <ul className="list-disc pl-5 text-sm">
                                                        {currentSelectedRepos.map(repo => <li key={repo}>{repo}</li>)}
                                                    </ul>
                                                ) : (
                                                    <p className="text-sm text-muted-foreground">(No repositories currently selected)</p>
                                                )}
                                                <Button type="button" variant="outline" size="sm" onClick={() => setEditMode('editing_repos')}>
                                                    <Edit className="mr-2 h-4 w-4" /> Change Selection / Update PAT
                                                </Button>
                                                <FormDescription>To change repo selections or update the PAT, click above.</FormDescription>
                                            </div>
                                        )}
                                        {editMode === 'editing_repos' && (
                                            <div className="space-y-4 p-4 border rounded-md">
                                                {/* PAT Input */}
                                                <div className="flex items-end gap-4 p-4 border rounded-md bg-muted/90">
                                                    <FormField control={patForm.control} name="github_pat" render={({ field }) => (
                                                        <FormItem className="flex-grow">
                                                            <FormLabel className="flex items-center gap-1"><KeyRound className="h-4 w-4" /> GitHub PAT</FormLabel>
                                                            <FormControl><Input type="password" placeholder="ghp_... or github_pat_..." {...field} /></FormControl>
                                                            <FormDescription>Enter PAT to fetch/update repos or if you need to update the stored token.</FormDescription>
                                                            <FormMessage />
                                                        </FormItem>
                                                    )} />
                                                    <Button type="button" disabled={isFetchingRepos} size="sm" onClick={async () => { const isValid = await patForm.trigger('github_pat'); if (isValid) { handleFetchRepositories(patForm.getValues()); } }}>
                                                        {isFetchingRepos ? <Loader2 className="h-4 w-4 animate-spin" /> : "Fetch Repositories"}
                                                    </Button>
                                                </div>
                                                {/* Repo List */}
                                                {isFetchingRepos && <Skeleton className="h-40 w-full" />}
                                                {!isFetchingRepos && fetchedRepos !== null && (
                                                    fetchedRepos.length === 0 ? (
                                                        <Alert variant="destructive"><CircleAlert className="h-4 w-4" /><AlertTitle>No Repositories Found</AlertTitle><AlertDescription>Check PAT & permissions.</AlertDescription></Alert>
                                                    ) : (
                                                        <div className="space-y-2">
                                                            <FormLabel>Select Repositories to Index ({newSelectedRepos.length} selected):</FormLabel>
                                                            <div className="h-64 w-full rounded-md border p-4 overflow-y-auto">
                                                                {fetchedRepos.map((repo) => (
                                                                    <div key={repo.id} className="flex items-center space-x-2 mb-2 py-1">
                                                                        <Checkbox id={`repo-${repo.id}`} checked={newSelectedRepos.includes(repo.full_name)} onCheckedChange={(checked) => handleRepoSelectionChange(repo.full_name, !!checked)} />
                                                                        <label htmlFor={`repo-${repo.id}`} className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">{repo.full_name} {repo.private && "(Private)"}</label>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )
                                                )}
                                                <Button type="button" variant="ghost" size="sm" onClick={() => { setEditMode('viewing'); setFetchedRepos(null); setNewSelectedRepos(currentSelectedRepos); patForm.reset({ github_pat: originalPat }); }}>
                                                    Cancel Repo Change
                                                </Button>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* == Slack == */}
                                {connector.connector_type === 'SLACK_CONNECTOR' && (
                                    <FormField
                                        control={editForm.control}
                                        name="SLACK_BOT_TOKEN"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel className="flex items-center gap-1"><KeyRound className="h-4 w-4" /> Slack Bot Token</FormLabel>
                                                <FormControl><Input type="password" placeholder="Begins with xoxb-..." {...field} /></FormControl>
                                                <FormDescription>Update the Slack Bot Token if needed.</FormDescription>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />
                                )}

                                {/* == Notion == */}
                                {connector.connector_type === 'NOTION_CONNECTOR' && (
                                    <FormField
                                        control={editForm.control}
                                        name="NOTION_INTEGRATION_TOKEN"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel className="flex items-center gap-1"><KeyRound className="h-4 w-4" /> Notion Integration Token</FormLabel>
                                                <FormControl><Input type="password" placeholder="Begins with secret_..." {...field} /></FormControl>
                                                <FormDescription>Update the Notion Integration Token if needed.</FormDescription>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />
                                )}

                                {/* == Serper API == */}
                                {connector.connector_type === 'SERPER_API' && (
                                    <FormField
                                        control={editForm.control}
                                        name="SERPER_API_KEY"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel className="flex items-center gap-1"><KeyRound className="h-4 w-4" /> Serper API Key</FormLabel>
                                                <FormControl><Input type="password" {...field} /></FormControl>
                                                <FormDescription>Update the Serper API Key if needed.</FormDescription>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />
                                )}

                                {/* == Tavily API == */}
                                {connector.connector_type === 'TAVILY_API' && (
                                    <FormField
                                        control={editForm.control}
                                        name="TAVILY_API_KEY"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel className="flex items-center gap-1"><KeyRound className="h-4 w-4" /> Tavily API Key</FormLabel>
                                                <FormControl><Input type="password" {...field} /></FormControl>
                                                <FormDescription>Update the Tavily API Key if needed.</FormDescription>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />
                                )}

                            </CardContent>
                            <CardFooter className="border-t pt-6">
                                <Button type="submit" disabled={isSaving} className="w-full sm:w-auto">
                                    {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
                                    Save Changes
                                </Button>
                            </CardFooter>
                        </form>
                    </Form>
                </Card>
            </motion.div>
        </div>
    );
} 
