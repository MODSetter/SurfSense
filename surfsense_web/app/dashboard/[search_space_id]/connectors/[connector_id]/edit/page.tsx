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

// Schema for PAT input when editing repos
const githubPatSchema = z.object({
    github_pat: z.string()
        .min(20, { message: "GitHub Personal Access Token seems too short." })
        .refine(pat => pat.startsWith('ghp_') || pat.startsWith('github_pat_'), {
            message: "GitHub PAT should start with 'ghp_' or 'github_pat_'",
        }),
});
type GithubPatFormValues = z.infer<typeof githubPatSchema>;

// Schema for main edit form (just the name for now)
const editConnectorSchema = z.object({
    name: z.string().min(3, { message: "Connector name must be at least 3 characters." }),
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

type EditMode = 'viewing' | 'editing_repos';

export default function EditGithubConnectorPage() {
    const router = useRouter();
    const params = useParams();
    const searchSpaceId = params.search_space_id as string;
    const connectorId = parseInt(params.connector_id as string, 10);

    const { connectors, updateConnector, isLoading: connectorsLoading } = useSearchSourceConnectors();

    const [connector, setConnector] = useState<SearchSourceConnector | null>(null);
    const [currentSelectedRepos, setCurrentSelectedRepos] = useState<string[]>([]);
    const [originalPat, setOriginalPat] = useState<string>(""); // State to hold the initial PAT
    const [editMode, setEditMode] = useState<EditMode>('viewing');
    const [fetchedRepos, setFetchedRepos] = useState<GithubRepo[] | null>(null); // Null indicates not fetched yet for edit
    const [newSelectedRepos, setNewSelectedRepos] = useState<string[]>([]); // Tracks selections *during* edit
    const [isFetchingRepos, setIsFetchingRepos] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    // Form for just the PAT input
    const patForm = useForm<GithubPatFormValues>({
        resolver: zodResolver(githubPatSchema),
        defaultValues: { github_pat: "" }, // Default empty, will be reset
    });

    // Form for the main connector details (e.g., name)
    const editForm = useForm<EditConnectorFormValues>({
        resolver: zodResolver(editConnectorSchema),
        defaultValues: { name: "" },
    });

    // Effect to find and set the current connector details on load
    useEffect(() => {
        if (!connectorsLoading && connectors.length > 0 && !connector) { // Added !connector check to prevent loop
            const currentConnector = connectors.find(c => c.id === connectorId);
            if (currentConnector && currentConnector.connector_type === 'GITHUB_CONNECTOR') {
                setConnector(currentConnector);
                const savedRepos = currentConnector.config?.repo_full_names || [];
                const savedPat = currentConnector.config?.GITHUB_PAT || "";
                setCurrentSelectedRepos(savedRepos);
                setNewSelectedRepos(savedRepos);
                setOriginalPat(savedPat); // Store the original PAT
                editForm.reset({ name: currentConnector.name });
                patForm.reset({ github_pat: savedPat }); // Also reset PAT form initially
            } else if (currentConnector) {
                toast.error("This connector is not a GitHub connector.");
                router.push(`/dashboard/${searchSpaceId}/connectors`);
            } else {
                toast.error("Connector not found.");
                router.push(`/dashboard/${searchSpaceId}/connectors`);
            }
        }
    }, [connectorId, connectors, connectorsLoading, router, searchSpaceId, connector]); // Removed editForm, patForm from dependencies

    // Fetch repositories using the entered PAT
    const handleFetchRepositories = async (values: GithubPatFormValues) => {
        setIsFetchingRepos(true);
        setFetchedRepos(null);
        // No need for patInputValue state, values.github_pat has the submitted value
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
            // Reset selection based on currently SAVED repos when fetching
            setNewSelectedRepos(currentSelectedRepos);
            toast.success(`Found ${data.length} repositories. Select which ones to index.`);
        } catch (error) {
            console.error("Error fetching GitHub repositories:", error);
            toast.error(error instanceof Error ? error.message : "Failed to fetch repositories.");
            // Don't clear PAT form on error, let user fix it
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

    // Save all changes (name and potentially repo selection + PAT)
    const handleSaveChanges = async (formData: EditConnectorFormValues) => {
        if (!connector) return;

        setIsSaving(true);
        const updatePayload: Partial<SearchSourceConnector> = {};
        let configChanged = false;

        // 1. Check if name changed
        if (formData.name !== connector.name) {
            updatePayload.name = formData.name;
        }

        // 2. Check PAT and Repo changes
        const currentPatInForm = patForm.getValues('github_pat');
        let patChanged = false;

        // Check if PAT input field was actually edited
        if (editMode === 'editing_repos' && currentPatInForm !== originalPat) {
            patChanged = true;
        }

        // Check if repo selection was modified
        const initialRepoSet = new Set(currentSelectedRepos);
        const newRepoSet = new Set(newSelectedRepos);
        const reposChanged = initialRepoSet.size !== newRepoSet.size || ![...initialRepoSet].every(repo => newRepoSet.has(repo));

        // If PAT was changed OR repos were changed (implying PAT was involved)
        if (patChanged || (editMode === 'editing_repos' && reposChanged && fetchedRepos !== null)) {
            // Validate the PAT from the form before including it
            if (!currentPatInForm || !(currentPatInForm.startsWith('ghp_') || currentPatInForm.startsWith('github_pat_'))) {
                toast.error("Invalid GitHub PAT format in the input field. Cannot save config changes.");
                setIsSaving(false);
                return;
            }

            updatePayload.config = {
                // Use the PAT value currently in the form field
                GITHUB_PAT: currentPatInForm,
                // Use the latest repo selection state
                repo_full_names: newSelectedRepos,
            };
            configChanged = true; // Mark config as changed

            if (reposChanged && newSelectedRepos.length === 0) {
                toast.warning("Warning: You haven't selected any repositories. The connector won't index anything.");
            }
        }

        // 3. Check if there are actual changes to save
        if (Object.keys(updatePayload).length === 0) {
            toast.info("No changes detected.");
            setIsSaving(false);
            setEditMode('viewing');
            // Reset PAT form to original value if returning to view mode without saving PAT change
            patForm.reset({ github_pat: originalPat });
            return;
        }

        // 4. Proceed with update API call
        try {
            await updateConnector(connectorId, updatePayload);
            toast.success("Connector updated successfully!");

            // Update local state based on what was *actually* saved
            if (updatePayload.config) {
                setCurrentSelectedRepos(updatePayload.config.repo_full_names || []);
                setOriginalPat(updatePayload.config.GITHUB_PAT || "");
                // Reset PAT form with the newly saved PAT
                patForm.reset({ github_pat: updatePayload.config.GITHUB_PAT || "" });
            } else {
                // If config wasn't in payload, ensure PAT form is reset to original value
                patForm.reset({ github_pat: originalPat });
            }
            // Update connector name state if it changed (or rely on hook refresh)
            if (updatePayload.name) {
                setConnector(prev => prev ? { ...prev, name: updatePayload.name! } : null);
            }

            // Reset edit state
            setEditMode('viewing');
            setFetchedRepos(null);
            // Reset working selection to match saved state (use the updated currentSelectedRepos)
            setNewSelectedRepos(updatePayload.config?.repo_full_names || currentSelectedRepos);

            // Optionally redirect or rely on hook refresh
            // router.push(`/dashboard/${searchSpaceId}/connectors`);

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
                        <CardTitle className="text-2xl font-bold flex items-center gap-2"><Github className="h-6 w-6" /> Edit GitHub Connector</CardTitle>
                        <CardDescription>
                            Modify the connector name and repository selections. To change repository selections, you need to re-enter your PAT.
                        </CardDescription>
                    </CardHeader>

                    {/* Use editForm for the main form structure */}
                    <Form {...editForm}>
                        <form onSubmit={editForm.handleSubmit(handleSaveChanges)} className="space-y-6">
                            <CardContent className="space-y-6">
                                {/* Connector Name Field */}
                                <FormField
                                    control={editForm.control}
                                    name="name"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Connector Name</FormLabel>
                                            <FormControl>
                                                <Input {...field} />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <hr />

                                {/* Repository Selection Section */}
                                <div className="space-y-4">
                                    <h3 className="text-lg font-semibold flex items-center gap-2"><ListChecks className="h-5 w-5" /> Repository Selection</h3>

                                    {editMode === 'viewing' && (
                                        <div className="space-y-3 p-4 border rounded-md bg-muted/50">
                                            <FormLabel>Currently Indexed Repositories:</FormLabel>
                                            {currentSelectedRepos.length > 0 ? (
                                                <ul className="list-disc pl-5 text-sm">
                                                    {currentSelectedRepos.map(repo => <li key={repo}>{repo}</li>)}
                                                </ul>
                                            ) : (
                                                <p className="text-sm text-muted-foreground">(No repositories currently selected for indexing)</p>
                                            )}
                                            <Button type="button" variant="outline" size="sm" onClick={() => setEditMode('editing_repos')}>
                                                <Edit className="mr-2 h-4 w-4" />
                                                Change Selection
                                            </Button>
                                            <FormDescription>Click "Change Selection" to re-enter your PAT and update the list.</FormDescription>
                                        </div>
                                    )}

                                    {editMode === 'editing_repos' && (
                                        <div className="space-y-4 p-4 border rounded-md">
                                            {/* PAT Input Section (No nested Form provider) */}
                                            {/* We still use patForm fields but trigger validation manually */}
                                            <div className="flex items-end gap-4 p-4 border rounded-md bg-muted/90">
                                                <FormField
                                                    // Associate with patForm instance for control/state
                                                    control={patForm.control}
                                                    name="github_pat"
                                                    render={({ field }) => (
                                                        <FormItem className="flex-grow">
                                                            <FormLabel className="flex items-center gap-1"><KeyRound className="h-4 w-4" /> Re-enter PAT to Fetch Repos</FormLabel>
                                                            <FormControl>
                                                                <Input type="password" placeholder="ghp_... or github_pat_..." {...field} />
                                                            </FormControl>
                                                            <FormMessage />
                                                        </FormItem>
                                                    )}
                                                />
                                                <Button
                                                    type="button" // Changed from submit to button
                                                    disabled={isFetchingRepos}
                                                    size="sm"
                                                    onClick={async () => { // Added async onClick handler
                                                        const isValid = await patForm.trigger('github_pat'); // Trigger validation
                                                        if (isValid) {
                                                            handleFetchRepositories(patForm.getValues()); // Call fetch if valid
                                                        }
                                                    }}
                                                >
                                                    {isFetchingRepos ? <Loader2 className="h-4 w-4 animate-spin" /> : "Fetch"}
                                                </Button>
                                            </div>

                                            {/* Fetched Repository List (shown after fetch) */}
                                            {isFetchingRepos && <Skeleton className="h-40 w-full" />}
                                            {!isFetchingRepos && fetchedRepos !== null && (
                                                fetchedRepos.length === 0 ? (
                                                    <Alert variant="destructive">
                                                        <CircleAlert className="h-4 w-4" />
                                                        <AlertTitle>No Repositories Found</AlertTitle>
                                                        <AlertDescription>Check the PAT and permissions.</AlertDescription>
                                                    </Alert>
                                                ) : (
                                                    <div className="space-y-2">
                                                        <FormLabel>Select Repositories to Index ({newSelectedRepos.length} selected):</FormLabel>
                                                        <div className="h-64 w-full rounded-md border p-4 overflow-y-auto">
                                                            {fetchedRepos.map((repo) => (
                                                                <div key={repo.id} className="flex items-center space-x-2 mb-2 py-1">
                                                                    <Checkbox
                                                                        id={`repo-${repo.id}`}
                                                                        checked={newSelectedRepos.includes(repo.full_name)}
                                                                        onCheckedChange={(checked) => handleRepoSelectionChange(repo.full_name, !!checked)}
                                                                    />
                                                                    <label
                                                                        htmlFor={`repo-${repo.id}`}
                                                                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                                                    >
                                                                        {repo.full_name} {repo.private && "(Private)"}
                                                                    </label>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )
                                            )}
                                            <Button type="button" variant="ghost" size="sm" onClick={() => {
                                                setEditMode('viewing');
                                                setFetchedRepos(null);
                                                setNewSelectedRepos(currentSelectedRepos);
                                                patForm.reset({ github_pat: originalPat }); // Reset PAT form on cancel
                                            }}>
                                                Cancel Repo Change
                                            </Button>
                                        </div>
                                    )}
                                </div>

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
