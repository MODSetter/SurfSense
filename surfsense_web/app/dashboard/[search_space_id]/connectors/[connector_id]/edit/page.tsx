"use client";

import { ArrowLeft, Check, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { toast } from "sonner";
import { EditConnectorLoadingSkeleton } from "@/components/editConnector/EditConnectorLoadingSkeleton";
import { EditConnectorNameForm } from "@/components/editConnector/EditConnectorNameForm";
import { EditGitHubConnectorConfig } from "@/components/editConnector/EditGitHubConnectorConfig";
import { EditSimpleTokenForm } from "@/components/editConnector/EditSimpleTokenForm";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useConnectorEditPage } from "@/hooks/use-connector-edit-page";
// Import Utils, Types, Hook, and Components
import { getConnectorTypeDisplay } from "@/lib/connectors/utils";

export default function EditConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	// Ensure connectorId is parsed safely
	const connectorIdParam = params.connector_id as string;
	const connectorId = connectorIdParam ? parseInt(connectorIdParam, 10) : NaN;

	// Use the custom hook to manage state and logic
	const {
		connectorsLoading,
		connector,
		isSaving,
		editForm,
		patForm, // Needed for GitHub child component
		handleSaveChanges,
		// GitHub specific props for the child component
		editMode,
		setEditMode, // Pass down if needed by GitHub component
		originalPat,
		currentSelectedRepos,
		fetchedRepos,
		setFetchedRepos,
		newSelectedRepos,
		setNewSelectedRepos,
		isFetchingRepos,
		handleFetchRepositories,
		handleRepoSelectionChange,
	} = useConnectorEditPage(connectorId, searchSpaceId);

	// Redirect if connectorId is not a valid number after parsing
	useEffect(() => {
		if (Number.isNaN(connectorId)) {
			toast.error("Invalid Connector ID.");
			router.push(`/dashboard/${searchSpaceId}/connectors`);
		}
	}, [connectorId, router, searchSpaceId]);

	// Loading State
	if (connectorsLoading || !connector) {
		// Handle NaN case before showing skeleton
		if (Number.isNaN(connectorId)) return null;
		return <EditConnectorLoadingSkeleton />;
	}

	// Main Render using data/handlers from the hook
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
						<CardDescription>Modify connector name and configuration.</CardDescription>
					</CardHeader>

					<Form {...editForm}>
						{/* Pass hook's handleSaveChanges */}
						<form onSubmit={editForm.handleSubmit(handleSaveChanges)} className="space-y-6">
							<CardContent className="space-y-6">
								{/* Pass form control from hook */}
								<EditConnectorNameForm control={editForm.control} />

								<hr />

								<h3 className="text-lg font-semibold">Configuration</h3>

								{/* == GitHub == */}
								{connector.connector_type === "GITHUB_CONNECTOR" && (
									<EditGitHubConnectorConfig
										// Pass relevant state and handlers from hook
										editMode={editMode}
										setEditMode={setEditMode} // Pass setter if child manages mode
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

								{/* == Slack == */}
								{connector.connector_type === "SLACK_CONNECTOR" && (
									<EditSimpleTokenForm
										control={editForm.control}
										fieldName="SLACK_BOT_TOKEN"
										fieldLabel="Slack Bot Token"
										fieldDescription="Update the Slack Bot Token if needed."
										placeholder="Begins with xoxb-..."
									/>
								)}
								{/* == Notion == */}
								{connector.connector_type === "NOTION_CONNECTOR" && (
									<EditSimpleTokenForm
										control={editForm.control}
										fieldName="NOTION_INTEGRATION_TOKEN"
										fieldLabel="Notion Integration Token"
										fieldDescription="Update the Notion Integration Token if needed."
										placeholder="Begins with secret_..."
									/>
								)}
								{/* == Serper == */}
								{connector.connector_type === "SERPER_API" && (
									<EditSimpleTokenForm
										control={editForm.control}
										fieldName="SERPER_API_KEY"
										fieldLabel="Serper API Key"
										fieldDescription="Update the Serper API Key if needed."
									/>
								)}
								{/* == Tavily == */}
								{connector.connector_type === "TAVILY_API" && (
									<EditSimpleTokenForm
										control={editForm.control}
										fieldName="TAVILY_API_KEY"
										fieldLabel="Tavily API Key"
										fieldDescription="Update the Tavily API Key if needed."
									/>
								)}

								{/* == Linear == */}
								{connector.connector_type === "LINEAR_CONNECTOR" && (
									<EditSimpleTokenForm
										control={editForm.control}
										fieldName="LINEAR_API_KEY"
										fieldLabel="Linear API Key"
										fieldDescription="Update your Linear API Key if needed."
										placeholder="Begins with lin_api_..."
									/>
								)}

								{/* == Jira == */}
								{connector.connector_type === "JIRA_CONNECTOR" && (
									<div className="space-y-4">
										<EditSimpleTokenForm
											control={editForm.control}
											fieldName="JIRA_BASE_URL"
											fieldLabel="Jira Base URL"
											fieldDescription="Update your Jira instance URL if needed."
											placeholder="https://yourcompany.atlassian.net"
										/>
										<EditSimpleTokenForm
											control={editForm.control}
											fieldName="JIRA_EMAIL"
											fieldLabel="Jira Email"
											fieldDescription="Update your Atlassian account email if needed."
											placeholder="your.email@company.com"
										/>
										<EditSimpleTokenForm
											control={editForm.control}
											fieldName="JIRA_API_TOKEN"
											fieldLabel="Jira API Token"
											fieldDescription="Update your Jira API Token if needed."
											placeholder="Your Jira API Token"
										/>
									</div>
								)}

								{/* == Confluence == */}
								{connector.connector_type === "CONFLUENCE_CONNECTOR" && (
									<div className="space-y-4">
										<EditSimpleTokenForm
											control={editForm.control}
											fieldName="CONFLUENCE_BASE_URL"
											fieldLabel="Confluence Base URL"
											fieldDescription="Update your Confluence instance URL if needed."
											placeholder="https://yourcompany.atlassian.net"
										/>
										<EditSimpleTokenForm
											control={editForm.control}
											fieldName="CONFLUENCE_EMAIL"
											fieldLabel="Confluence Email"
											fieldDescription="Update your Atlassian account email if needed."
											placeholder="your.email@company.com"
										/>
										<EditSimpleTokenForm
											control={editForm.control}
											fieldName="CONFLUENCE_API_TOKEN"
											fieldLabel="Confluence API Token"
											fieldDescription="Update your Confluence API Token if needed."
											placeholder="Your Confluence API Token"
										/>
									</div>
								)}

								{/* == ClickUp == */}
								{connector.connector_type === "CLICKUP_CONNECTOR" && (
									<EditSimpleTokenForm
										control={editForm.control}
										fieldName="CLICKUP_API_TOKEN"
										fieldLabel="ClickUp API Token"
										fieldDescription="Update your ClickUp API Token if needed."
										placeholder="pk_..."
									/>
								)}

								{/* == Linkup == */}
								{connector.connector_type === "LINKUP_API" && (
									<EditSimpleTokenForm
										control={editForm.control}
										fieldName="LINKUP_API_KEY"
										fieldLabel="Linkup API Key"
										fieldDescription="Update your Linkup API Key if needed."
										placeholder="Begins with linkup_..."
									/>
								)}

								{/* == Discord == */}
								{connector.connector_type === "DISCORD_CONNECTOR" && (
									<EditSimpleTokenForm
										control={editForm.control}
										fieldName="DISCORD_BOT_TOKEN"
										fieldLabel="Discord Bot Token"
										fieldDescription="Update the Discord Bot Token if needed."
										placeholder="Bot token..."
									/>
								)}

								{/* == Luma == */}
								{connector.connector_type === "LUMA_CONNECTOR" && (
									<EditSimpleTokenForm
										control={editForm.control}
										fieldName="LUMA_API_KEY"
										fieldLabel="Luma API Key"
										fieldDescription="Update the Luma API Key if needed."
										placeholder="API Key..."
									/>
								)}

								{/* == Elasticsearch == */}
								{connector.connector_type === "ELASTICSEARCH_CONNECTOR" && (
									<EditSimpleTokenForm
										control={editForm.control}
										fieldName="ELASTICSEARCH_API_KEY"
										fieldLabel="Elasticsearch API Key"
										fieldDescription="Update your Elasticsearch API Key if needed."
										placeholder="Your Elasticsearch API Key"
									/>
								)}
							</CardContent>
							<CardFooter className="border-t pt-6">
								<Button type="submit" disabled={isSaving} className="w-full sm:w-auto">
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
				</Card>
			</motion.div>
		</div>
	);
}
