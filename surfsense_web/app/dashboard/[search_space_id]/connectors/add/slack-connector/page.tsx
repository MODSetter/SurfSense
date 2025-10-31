"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Check, Info, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
	Form,
	FormControl,
	FormDescription,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

// Define the form schema with Zod
const slackConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	bot_token: z.string().min(10, {
		message: "Bot User OAuth Token is required and must be valid.",
	}),
});

// Define the type for the form values
type SlackConnectorFormValues = z.infer<typeof slackConnectorFormSchema>;

export default function SlackConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form
	const form = useForm<SlackConnectorFormValues>({
		resolver: zodResolver(slackConnectorFormSchema),
		defaultValues: {
			name: "Slack Connector",
			bot_token: "",
		},
	});

	// Handle form submission
	const onSubmit = async (values: SlackConnectorFormValues) => {
		setIsSubmitting(true);
		try {
			await createConnector(
				{
					name: values.name,
					connector_type: EnumConnectorName.SLACK_CONNECTOR,
					config: {
						SLACK_BOT_TOKEN: values.bot_token,
					},
					is_indexable: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("Slack connector created successfully!");

			// Navigate back to connectors page
			router.push(`/dashboard/${searchSpaceId}/connectors`);
		} catch (error) {
			console.error("Error creating connector:", error);
			toast.error(error instanceof Error ? error.message : "Failed to create connector");
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div className="container mx-auto py-8 max-w-3xl">
			<Button
				variant="ghost"
				className="mb-6"
				onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/add`)}
			>
				<ArrowLeft className="mr-2 h-4 w-4" />
				Back to Connectors
			</Button>

			{/* Header */}
			<div className="mb-8">
				<div className="flex items-center gap-4">
					<div className="flex h-12 w-12 items-center justify-center rounded-lg">
						{getConnectorIcon(EnumConnectorName.SLACK_CONNECTOR, "h-6 w-6")}
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Connect Slack</h1>
						<p className="text-muted-foreground">
							Connect your Slack workspace to search messages and channels.
						</p>
					</div>
				</div>
			</div>

			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
			>
				<Tabs defaultValue="connect" className="w-full">
					<TabsList className="grid w-full grid-cols-2 mb-6">
						<TabsTrigger value="connect">Connect</TabsTrigger>
						<TabsTrigger value="documentation">Documentation</TabsTrigger>
					</TabsList>

					<TabsContent value="connect">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold">Connect Slack Workspace</CardTitle>
								<CardDescription>
									Integrate with Slack to search and retrieve information from your workspace
									channels and conversations. This connector can index your Slack messages for
									search.
								</CardDescription>
							</CardHeader>
							<CardContent>
								<Alert className="mb-6 bg-muted">
									<Info className="h-4 w-4" />
									<AlertTitle>Bot User OAuth Token Required</AlertTitle>
									<AlertDescription>
										You'll need a Slack Bot User OAuth Token to use this connector. You can create a
										Slack app and get the token from{" "}
										<a
											href="https://api.slack.com/apps"
											target="_blank"
											rel="noopener noreferrer"
											className="font-medium underline underline-offset-4"
										>
											Slack API Dashboard
										</a>
									</AlertDescription>
								</Alert>

								<Form {...form}>
									<form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
										<FormField
											control={form.control}
											name="name"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Connector Name</FormLabel>
													<FormControl>
														<Input placeholder="My Slack Connector" {...field} />
													</FormControl>
													<FormDescription>
														A friendly name to identify this connector.
													</FormDescription>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={form.control}
											name="bot_token"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Slack Bot User OAuth Token</FormLabel>
													<FormControl>
														<Input type="password" placeholder="xoxb-..." {...field} />
													</FormControl>
													<FormDescription>
														Your Bot User OAuth Token will be encrypted and stored securely. It
														typically starts with "xoxb-".
													</FormDescription>
													<FormMessage />
												</FormItem>
											)}
										/>

										<div className="flex justify-end">
											<Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
												{isSubmitting ? (
													<>
														<Loader2 className="mr-2 h-4 w-4 animate-spin" />
														Connecting...
													</>
												) : (
													<>
														<Check className="mr-2 h-4 w-4" />
														Connect Slack
													</>
												)}
											</Button>
										</div>
									</form>
								</Form>
							</CardContent>
							<CardFooter className="flex flex-col items-start border-t bg-muted/50 px-6 py-4">
								<h4 className="text-sm font-medium">What you get with Slack integration:</h4>
								<ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
									<li>Search through your Slack channels and conversations</li>
									<li>Access historical messages and shared files</li>
									<li>Connect your team's knowledge directly to your search space</li>
									<li>Keep your search results up-to-date with latest communications</li>
									<li>Index your Slack messages for enhanced search capabilities</li>
								</ul>
							</CardFooter>
						</Card>
					</TabsContent>

					<TabsContent value="documentation">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold">Slack Connector Documentation</CardTitle>
								<CardDescription>
									Learn how to set up and use the Slack connector to index your workspace data.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<div>
									<h3 className="text-xl font-semibold mb-2">How it works</h3>
									<p className="text-muted-foreground">
										The Slack connector indexes all public channels for a given workspace.
									</p>
									<ul className="mt-2 list-disc pl-5 text-muted-foreground">
										<li>
											Upcoming: Support for private channels by tagging/adding the Slack Bot to
											private channels.
										</li>
									</ul>
								</div>

								<Accordion type="single" collapsible className="w-full">
									<AccordionItem value="authorization">
										<AccordionTrigger className="text-lg font-medium">
											Authorization
										</AccordionTrigger>
										<AccordionContent className="space-y-4">
											<Alert className="bg-muted">
												<Info className="h-4 w-4" />
												<AlertTitle>Admin Access Required</AlertTitle>
												<AlertDescription>
													You must be an admin of the Slack workspace to set up the connector.
												</AlertDescription>
											</Alert>

											<ol className="list-decimal pl-5 space-y-3">
												<li>
													Navigate and sign in to{" "}
													<a
														href="https://api.slack.com/apps"
														target="_blank"
														rel="noopener noreferrer"
														className="font-medium underline underline-offset-4"
													>
														https://api.slack.com/apps
													</a>
													.
												</li>
												<li>
													Create a new Slack app:
													<ul className="list-disc pl-5 mt-1">
														<li>
															Click the <strong>Create New App</strong> button in the top right.
														</li>
														<li>
															Select <strong>From an app manifest</strong> option.
														</li>
														<li>
															Select the relevant workspace from the dropdown and click{" "}
															<strong>Next</strong>.
														</li>
													</ul>
												</li>
												<li>
													Select the "YAML" tab, paste the following manifest into the text box, and
													click <strong>Next</strong>:
													<div className="bg-muted p-4 rounded-md mt-2 overflow-x-auto">
														<pre className="text-xs">
															{`display_information:
  name: SlackConnector
  description: ReadOnly Connector for indexing
features:
  bot_user:
    display_name: SlackConnector
    always_online: false
oauth_config:
  scopes:
    bot:
      - channels:history
      - channels:read
      - groups:history
      - groups:read
      - channels:join
      - im:history
      - users:read
      - users:read.email
      - usergroups:read
settings:
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false`}
														</pre>
													</div>
												</li>
												<li>
													Click the <strong>Create</strong> button.
												</li>
												<li>
													In the app page, navigate to the <strong>OAuth & Permissions</strong> tab
													under the <strong>Features</strong> header.
												</li>
												<li>
													Copy the <strong>Bot User OAuth Token</strong>, this will be used to
													access Slack.
												</li>
											</ol>
										</AccordionContent>
									</AccordionItem>

									<AccordionItem value="indexing">
										<AccordionTrigger className="text-lg font-medium">Indexing</AccordionTrigger>
										<AccordionContent className="space-y-4">
											<ol className="list-decimal pl-5 space-y-3">
												<li>
													Navigate to the Connector Dashboard and select the <strong>Slack</strong>{" "}
													Connector.
												</li>
												<li>
													Place the <strong>Bot User OAuth Token</strong> under{" "}
													<strong>Step 1 Provide Credentials</strong>.
												</li>
												<li>
													Click <strong>Connect</strong> to establish the connection.
												</li>
											</ol>

											<Alert className="bg-muted">
												<Info className="h-4 w-4" />
												<AlertTitle>Important: Invite Bot to Channels</AlertTitle>
												<AlertDescription>
													After connecting, you must invite the bot to each channel you want to
													index. In each Slack channel, type:
													<pre className="mt-2 bg-background p-2 rounded-md text-xs">
														/invite @YourBotName
													</pre>
													<p className="mt-2">
														Without this step, you'll get a "not_in_channel" error when the
														connector tries to access channel messages.
													</p>
												</AlertDescription>
											</Alert>

											<Alert className="bg-muted mt-4">
												<Info className="h-4 w-4" />
												<AlertTitle>First Indexing</AlertTitle>
												<AlertDescription>
													The first indexing pulls all of the public channels and takes longer than
													future updates. Only channels where the bot has been invited will be fully
													indexed.
												</AlertDescription>
											</Alert>

											<div className="mt-4">
												<h4 className="font-medium mb-2">Troubleshooting:</h4>
												<ul className="list-disc pl-5 space-y-2 text-muted-foreground">
													<li>
														<strong>not_in_channel error:</strong> If you see this error in logs, it
														means the bot hasn't been invited to a channel it's trying to access.
														Use the <code>/invite @YourBotName</code> command in that channel.
													</li>
													<li>
														<strong>Alternative approach:</strong> You can add the{" "}
														<code>chat:write.public</code> scope to your Slack app to allow it to
														access public channels without an explicit invitation.
													</li>
													<li>
														<strong>For private channels:</strong> The bot must always be invited
														using the <code>/invite</code> command.
													</li>
												</ul>
											</div>
										</AccordionContent>
									</AccordionItem>
								</Accordion>
							</CardContent>
						</Card>
					</TabsContent>
				</Tabs>
			</motion.div>
		</div>
	);
}
