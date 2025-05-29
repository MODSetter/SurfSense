"use client";

import React, { useEffect, useState } from "react"; // Added useState
import { useRouter, useParams } from "next/navigation";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { ArrowLeft, Check, Loader2, Github, RefreshCw, Search } from "lucide-react"; // Added RefreshCw, Search

import { Form } from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

// Import Utils, Types, Hook, and Components
import { getConnectorTypeDisplay } from "@/lib/connectors/utils";
import { useConnectorEditPage } from "@/hooks/useConnectorEditPage";
import { EditConnectorLoadingSkeleton } from "@/components/editConnector/EditConnectorLoadingSkeleton";
import { EditConnectorNameForm } from "@/components/editConnector/EditConnectorNameForm";
import { EditGitHubConnectorConfig } from "@/components/editConnector/EditGitHubConnectorConfig";
import { EditSimpleTokenForm } from "@/components/editConnector/EditSimpleTokenForm";
import EditSlackConnectorConfigForm from '@/components/editConnector/EditSlackConnectorConfigForm'; // Corrected import
import { getConnectorIcon } from "@/components/chat";
import { SearchSourceConnector } from "@/hooks/useSearchSourceConnectors"; // For type

// Define type for discovered Slack channels (mirroring backend response)
interface SlackChannelInfo {
    id: string;
    name: string;
    is_private: boolean;
    is_member: boolean; // Assuming this is part of the discovery
}

export default function EditConnectorPage() {
    const router = useRouter();
    const params = useParams();
    const searchSpaceId = params.search_space_id as string;
    const connectorIdParam = params.connector_id as string;
    const connectorId = connectorIdParam ? parseInt(connectorIdParam, 10) : NaN;

    const {
        connectorsLoading,
        connector,
        isSaving,
        editForm,
        patForm,
        handleSaveChanges,
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
        // Placeholder functions that would ideally come from the hook
        // discoverSlackChannels: hookDiscoverSlackChannels, 
        // triggerSlackReindex: hookTriggerSlackReindex,
    } = useConnectorEditPage(connectorId, searchSpaceId);

    // State for Slack Channel Management
    const [activeTab, setActiveTab] = useState("configuration");
    const [discoveredChannels, setDiscoveredChannels] = useState<SlackChannelInfo[]>([]);
    const [selectedChannelsForConfig, setSelectedChannelsForConfig] = useState<Set<string>>(new Set());
    const [isDiscoveringChannels, setIsDiscoveringChannels] = useState(false);
    
    // State for On-Demand Re-indexing
    const [selectedChannelsForReindex, setSelectedChannelsForReindex] = useState<Set<string>>(new Set());
    const [forceReindexAllMessages, setForceReindexAllMessages] = useState(false);
    const [reindexStartDate, setReindexStartDate] = useState<string>(""); // YYYY-MM-DD
    const [reindexLatestDate, setReindexLatestDate] = useState<string>(""); // YYYY-MM-DD
    const [isReindexing, setIsReindexing] = useState(false);

    useEffect(() => {
        if (isNaN(connectorId)) {
            toast.error("Invalid Connector ID.");
            router.push(`/dashboard/${searchSpaceId}/connectors`);
        }
    }, [connectorId, router, searchSpaceId]);

    useEffect(() => {
        if (connector?.config?.slack_selected_channel_ids) {
            setSelectedChannelsForConfig(new Set(connector.config.slack_selected_channel_ids));
        }
    }, [connector?.config?.slack_selected_channel_ids]);


    // Placeholder for discoverSlackChannels API call
    const handleDiscoverChannels = async () => {
        setIsDiscoveringChannels(true);
        toast.info("Discovering Slack channels...");
        // Replace with actual API call:
        // const channels = await hookDiscoverSlackChannels(connectorId);
        // For now, using mock data:
        await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate API delay
        const mockChannels: SlackChannelInfo[] = [
            { id: "C123", name: "general", is_private: false, is_member: true },
            { id: "C456", name: "random", is_private: false, is_member: true },
            { id: "C789", name: "dev-team-private", is_private: true, is_member: true },
            { id: "CABC", name: "marketing", is_private: false, is_member: false }, // Bot not member
        ];
        const memberChannels = mockChannels.filter(ch => ch.is_member);
        setDiscoveredChannels(memberChannels);
        if (memberChannels.length > 0) {
            toast.success(`Discovered ${memberChannels.length} channels where bot is a member.`);
        } else {
            toast.warning("No channels found where the bot is a member, or discovery failed.");
        }
        setIsDiscoveringChannels(false);
    };

    const handleChannelSelectionForConfig = (channelId: string, isSelected: boolean) => {
        const newSelection = new Set(selectedChannelsForConfig);
        if (isSelected) {
            newSelection.add(channelId);
        } else {
            newSelection.delete(channelId);
        }
        setSelectedChannelsForConfig(newSelection);
    };

    const handleSaveChannelSelection = () => {
        const currentFullConfig = editForm.getValues('config') || {};
        const newConfig = {
            ...currentFullConfig,
            slack_selected_channel_ids: Array.from(selectedChannelsForConfig),
        };
        editForm.setValue('config', newConfig, { shouldValidate: true, shouldDirty: true });
        toast.success("Channel selection updated. Save changes to persist.");
        // Note: This only updates the form state. The main "Save Changes" button persists it.
    };
    
    const handleChannelSelectionForReindex = (channelId: string, isSelected: boolean) => {
        const newSelection = new Set(selectedChannelsForReindex);
        if (isSelected) {
            newSelection.add(channelId);
        } else {
            newSelection.delete(channelId);
        }
        setSelectedChannelsForReindex(newSelection);
    };

    // Placeholder for triggerSlackReindex API call
    const handleTriggerReindex = async () => {
        if (selectedChannelsForReindex.size === 0) {
            toast.warning("Please select at least one channel to re-index.");
            return;
        }
        setIsReindexing(true);
        toast.info("Triggering re-indexing for selected channels...");
        const payload = {
            channel_ids: Array.from(selectedChannelsForReindex),
            force_reindex_all_messages: forceReindexAllMessages,
            reindex_start_date: reindexStartDate || null, // Ensure null if empty
            reindex_latest_date: reindexLatestDate || null, // Ensure null if empty
        };
        // Replace with actual API call:
        // await hookTriggerSlackReindex(connectorId, payload);
        console.log("Re-indexing payload:", payload);
        await new Promise(resolve => setTimeout(resolve, 2000)); // Simulate API delay
        toast.success("Re-indexing task scheduled successfully.");
        setIsReindexing(false);
        // Clear selections after triggering
        setSelectedChannelsForReindex(new Set());
        setForceReindexAllMessages(false);
        setReindexStartDate("");
        setReindexLatestDate("");
    };


    if (connectorsLoading || !connector) {
        if (isNaN(connectorId)) return null;
        return <EditConnectorLoadingSkeleton />;
    }
    
    const isSlackConnector = connector.connector_type === "SLACK_CONNECTOR";
    const configMembershipType = editForm.watch('config.slack_membership_filter_type', connector?.config?.slack_membership_filter_type);


    return (
        <div className="container mx-auto py-8 max-w-3xl">
            <Button
                variant="ghost"
                className="mb-6"
                onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors`)}
            >
                <ArrowLeft className="mr-2 h-4 w-4" /> Back to Connectors
            </Button>

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
            >
                <Card className="border-2 border-border">
                    <CardHeader>
                        <CardTitle className="text-2xl font-bold flex items-center gap-2">
                            {getConnectorIcon(connector.connector_type)}
                            Edit {getConnectorTypeDisplay(connector.connector_type)} Connector
                        </CardTitle>
                        <CardDescription>
                            Modify connector name, configuration, and manage channels.
                        </CardDescription>
                    </CardHeader>

                    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                        <TabsList className="grid w-full grid-cols-2 mb-4">
                            <TabsTrigger value="configuration">Configuration</TabsTrigger>
                            <TabsTrigger value="channel_management" disabled={!isSlackConnector}>Channel Management</TabsTrigger>
                        </TabsList>

                        <TabsContent value="configuration">
                            <Form {...editForm}>
                                <form
                                    onSubmit={editForm.handleSubmit(handleSaveChanges)}
                                    className="space-y-6"
                                >
                                    <CardContent className="space-y-6">
                                        <EditConnectorNameForm control={editForm.control} />
                                        <hr />
                                        <h3 className="text-lg font-semibold">Configuration Details</h3>

                                        {connector.connector_type === "GITHUB_CONNECTOR" && (
                                            <EditGitHubConnectorConfig
                                                editMode={editMode}
                                                setEditMode={setEditMode}
                                                originalPat={originalPat}
                                                currentSelectedRepos={currentSelectedRepos}
                                                fetchedRepos={fetchedRepos}
                                                newSelectedRepos={newSelectedRepos}
                                                isFetchingRepos={isFetchingRepos}
                                                patForm={patForm}
                                                handleFetchRepositories={handleFetchRepositories}
                                                handleRepoSelectionChange={handleRepoSelectionChange}
                                                setNewSelectedRepos={setNewSelectedRepos}
                                                setFetchedRepos={setFetchedRepos}
                                            />
                                        )}

                                        {isSlackConnector && (
                                            <EditSlackConnectorConfigForm
                                                connector={connector}
                                                onConfigChange={(newConfig) => editForm.setValue('config', newConfig, { shouldValidate: true, shouldDirty: true })}
                                                disabled={isSaving}
                                            />
                                        )}
                                        {connector.connector_type === "NOTION_CONNECTOR" && (
                                            <EditSimpleTokenForm
                                                control={editForm.control}
                                                fieldName="NOTION_INTEGRATION_TOKEN"
                                                fieldLabel="Notion Integration Token"
                                                fieldDescription="Update the Notion Integration Token if needed."
                                                placeholder="Begins with secret_..."
                                            />
                                        )}
                                        {connector.connector_type === "SERPER_API" && (
                                            <EditSimpleTokenForm
                                                control={editForm.control}
                                                fieldName="SERPER_API_KEY"
                                                fieldLabel="Serper API Key"
                                                fieldDescription="Update the Serper API Key if needed."
                                            />
                                        )}
                                        {connector.connector_type === "TAVILY_API" && (
                                            <EditSimpleTokenForm
                                                control={editForm.control}
                                                fieldName="TAVILY_API_KEY"
                                                fieldLabel="Tavily API Key"
                                                fieldDescription="Update the Tavily API Key if needed."
                                            />
                                        )}
                                        {connector.connector_type === "LINEAR_CONNECTOR" && (
                                            <EditSimpleTokenForm
                                                control={editForm.control}
                                                fieldName="LINEAR_API_KEY"
                                                fieldLabel="Linear API Key"
                                                fieldDescription="Update your Linear API Key if needed."
                                                placeholder="Begins with lin_api_..."
                                            />
                                        )}
                                        {connector.connector_type === "LINKUP_API" && (
                                            <EditSimpleTokenForm
                                                control={editForm.control}
                                                fieldName="LINKUP_API_KEY"
                                                fieldLabel="Linkup API Key"
                                                fieldDescription="Update your Linkup API Key if needed."
                                                placeholder="Begins with linkup_..."
                                            />
                                        )}
                                    </CardContent>
                                    <CardFooter className="border-t pt-6">
                                        <Button
                                            type="submit"
                                            disabled={isSaving}
                                            className="w-full sm:w-auto"
                                        >
                                            {isSaving ? (
                                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                            ) : (
                                                <Check className="mr-2 h-4 w-4" />
                                            )}
                                            Save Changes
                                        </Button>
                                    </CardFooter>
                                </form>
                            </Form>
                        </TabsContent>

                        <TabsContent value="channel_management">
                            {isSlackConnector ? (
                                <CardContent className="space-y-6">
                                    <section className="space-y-4 p-4 border rounded-lg">
                                        <h4 className="text-md font-semibold">Granular Channel Selection</h4>
                                        {configMembershipType === 'selected_member_channels' ? (
                                            <>
                                                <Button onClick={handleDiscoverChannels} disabled={isDiscoveringChannels || isSaving}>
                                                    {isDiscoveringChannels ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
                                                    Discover & Select Channels
                                                </Button>
                                                {discoveredChannels.length > 0 && (
                                                    <div className="space-y-3">
                                                        <div className="max-h-60 overflow-y-auto border rounded-md">
                                                            <Table>
                                                                <TableHeader>
                                                                    <TableRow>
                                                                        <TableHead className="w-[50px]"></TableHead>
                                                                        <TableHead>Channel Name</TableHead>
                                                                        <TableHead>ID</TableHead>
                                                                        <TableHead>Visibility</TableHead>
                                                                    </TableRow>
                                                                </TableHeader>
                                                                <TableBody>
                                                                    {discoveredChannels.map((channel) => (
                                                                        <TableRow key={channel.id}>
                                                                            <TableCell>
                                                                                <Checkbox
                                                                                    checked={selectedChannelsForConfig.has(channel.id)}
                                                                                    onCheckedChange={(checked) => handleChannelSelectionForConfig(channel.id, !!checked)}
                                                                                    disabled={isSaving}
                                                                                />
                                                                            </TableCell>
                                                                            <TableCell>{channel.name}</TableCell>
                                                                            <TableCell>{channel.id}</TableCell>
                                                                            <TableCell>{channel.is_private ? "Private" : "Public"}</TableCell>
                                                                        </TableRow>
                                                                    ))}
                                                                </TableBody>
                                                            </Table>
                                                        </div>
                                                        <Button onClick={handleSaveChannelSelection} disabled={isSaving}>
                                                            Update Channel Selection in Config
                                                        </Button>
                                                        <p className="text-xs text-muted-foreground">
                                                            This updates the selection for the main configuration. Remember to click "Save Changes" at the bottom to persist.
                                                        </p>
                                                    </div>
                                                )}
                                            </>
                                        ) : (
                                            <Alert>
                                                <AlertTitle>All Channels Mode</AlertTitle>
                                                <AlertDescription>
                                                    Currently configured to index all channels where the bot is a member. 
                                                    To select specific channels, change "Channel Indexing Behavior" to "Index Only Selected Channels" in the Configuration tab and save changes.
                                                </AlertDescription>
                                            </Alert>
                                        )}
                                    </section>

                                    <hr/>

                                    <section className="space-y-4 p-4 border rounded-lg">
                                        <h4 className="text-md font-semibold">On-Demand Re-indexing</h4>
                                        <p className="text-sm text-muted-foreground">
                                           Select channels from the list above (if discovered) or previously configured channels to re-index.
                                           If no channels are discovered/displayed, re-indexing will apply to channels currently saved in the configuration.
                                        </p>
                                        
                                        {/* Re-indexing Table - Show selected channels or all discovered ones */}
                                        <div className="max-h-60 overflow-y-auto border rounded-md">
                                            <Table>
                                                <TableHeader>
                                                    <TableRow>
                                                        <TableHead className="w-[50px]"></TableHead>
                                                        <TableHead>Channel Name</TableHead>
                                                        <TableHead>ID</TableHead>
                                                    </TableRow>
                                                </TableHeader>
                                                <TableBody>
                                                    {(discoveredChannels.length > 0 ? discoveredChannels : 
                                                      (connector.config?.slack_selected_channel_ids || []).map((id: string) => ({id, name: `Known ID: ${id}`, is_private: false, is_member: true})) 
                                                    ).map((channel: SlackChannelInfo | {id: string, name: string}) => (
                                                        <TableRow key={channel.id}>
                                                            <TableCell>
                                                                <Checkbox
                                                                    checked={selectedChannelsForReindex.has(channel.id)}
                                                                    onCheckedChange={(checked) => handleChannelSelectionForReindex(channel.id, !!checked)}
                                                                    disabled={isReindexing || isSaving}
                                                                />
                                                            </TableCell>
                                                            <TableCell>{channel.name}</TableCell>
                                                            <TableCell>{channel.id}</TableCell>
                                                        </TableRow>
                                                    ))}
                                                </TableBody>
                                            </Table>
                                        </div>
                                        
                                        <div className="flex items-center space-x-2 mt-2">
                                            <Checkbox
                                                id="forceReindexAllMessages"
                                                checked={forceReindexAllMessages}
                                                onCheckedChange={(checked) => setForceReindexAllMessages(!!checked)}
                                                disabled={isReindexing || isSaving}
                                            />
                                            <Label htmlFor="forceReindexAllMessages">Full Re-index (ignore last sync date)?</Label>
                                        </div>

                                        {forceReindexAllMessages && (
                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
                                                <div className="space-y-1">
                                                    <Label htmlFor="reindexStartDate">Re-index Start Date (Optional)</Label>
                                                    <Input
                                                        id="reindexStartDate"
                                                        type="date"
                                                        value={reindexStartDate}
                                                        onChange={(e) => setReindexStartDate(e.target.value)}
                                                        disabled={isReindexing || isSaving}
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <Label htmlFor="reindexLatestDate">Re-index Latest Date (Optional)</Label>
                                                    <Input
                                                        id="reindexLatestDate"
                                                        type="date"
                                                        value={reindexLatestDate}
                                                        onChange={(e) => setReindexLatestDate(e.target.value)}
                                                        disabled={isReindexing || isSaving}
                                                    />
                                                </div>
                                            </div>
                                        )}
                                        <Button onClick={handleTriggerReindex} disabled={isReindexing || isSaving || selectedChannelsForReindex.size === 0}>
                                            {isReindexing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                                            Re-index Selected Channels ({selectedChannelsForReindex.size})
                                        </Button>
                                    </section>
                                </CardContent>
                            ) : (
                                <CardContent>
                                    <p className="text-muted-foreground">Channel management is specific to Slack connectors.</p>
                                </CardContent>
                            )}
                        </TabsContent>
                    </Tabs>
                </Card>
            </motion.div>
        </div>
    );
}
