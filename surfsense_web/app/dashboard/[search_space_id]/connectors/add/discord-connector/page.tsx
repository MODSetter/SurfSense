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
const discordConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	bot_token: z
		.string()
		.min(50, { message: "Discord Bot Token appears to be too short." })
		.regex(/^[A-Za-z0-9._-]+$/, { message: "Discord Bot Token contains invalid characters." }),
});

// Define the type for the form values
type DiscordConnectorFormValues = z.infer<typeof discordConnectorFormSchema>;

export default function DiscordConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form
	const form = useForm<DiscordConnectorFormValues>({
		resolver: zodResolver(discordConnectorFormSchema),
		defaultValues: {
			name: "Discord Connector",
			bot_token: "",
		},
	});

	// Handle form submission
	const onSubmit = async (values: DiscordConnectorFormValues) => {
		setIsSubmitting(true);
		try {
			await createConnector(
				{
					name: values.name,
					connector_type: EnumConnectorName.DISCORD_CONNECTOR,
					config: {
						DISCORD_BOT_TOKEN: values.bot_token,
					},
					is_indexable: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("Discord connector created successfully!");
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
					<div className="flex h-12 w-12 items-center justify-center rounded-lg ">
						{getConnectorIcon(EnumConnectorName.DISCORD_CONNECTOR, "h-6 w-6")}
					</div>
					<div>
						<h1 className="text-3xl font-bold tracking-tight">Connect Discord</h1>
						<p className="text-muted-foreground">
							Connect your Discord server to search messages and channels.
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
								<CardTitle className="text-2xl font-bold">Connect Discord Server</CardTitle>
								<CardDescription>
									Integrate with Discord to search and retrieve information from your servers and
									channels. This connector can index your Discord messages for search.
								</CardDescription>
							</CardHeader>
							<CardContent>
								<Alert className="mb-6 bg-muted">
									<Info className="h-4 w-4" />
									<AlertTitle>Bot Token Required</AlertTitle>
									<AlertDescription>
										You'll need a Discord Bot Token to use this connector. You can create a Discord
										bot and get the token from the{" "}
										<a
											href="https://discord.com/developers/applications"
											target="_blank"
											rel="noopener noreferrer"
											className="font-medium underline underline-offset-4"
										>
											Discord Developer Portal
										</a>
										.
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
														<Input placeholder="My Discord Connector" {...field} />
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
													<FormLabel>Discord Bot Token</FormLabel>
													<FormControl>
														<Input type="password" placeholder="Bot Token..." {...field} />
													</FormControl>
													<FormDescription>
														Your Discord Bot Token will be encrypted and stored securely. You can
														find it in the Bot section of your application in the Discord Developer
														Portal.
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
														Connect Discord
													</>
												)}
											</Button>
										</div>
									</form>
								</Form>
							</CardContent>
							<CardFooter className="flex flex-col items-start border-t bg-muted/50 px-6 py-4">
								<h4 className="text-sm font-medium">What you get with Discord integration:</h4>
								<ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
									<li>Search through your Discord servers and channels</li>
									<li>Access historical messages and shared files</li>
									<li>Connect your team's knowledge directly to your search space</li>
									<li>Keep your search results up-to-date with latest communications</li>
									<li>Index your Discord messages for enhanced search capabilities</li>
								</ul>
							</CardFooter>
						</Card>
					</TabsContent>

					<TabsContent value="documentation">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold">
									Discord Connector Documentation
								</CardTitle>
								<CardDescription>
									Learn how to set up and use the Discord connector to index your server data.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<div>
									<h3 className="text-xl font-semibold mb-2">How it works</h3>
									<p className="text-muted-foreground">
										The Discord connector indexes all accessible channels for a given bot in your
										servers.
									</p>
									<ul className="mt-2 list-disc pl-5 text-muted-foreground">
										<li>Upcoming: Support for private channels by granting the bot access.</li>
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
												<AlertTitle>Bot Setup Required</AlertTitle>
												<AlertDescription>
													You must create a Discord bot and add it to your server with the correct
													permissions.
												</AlertDescription>
											</Alert>

											<ol className="list-decimal pl-5 space-y-3">
												<li>
													Go to{" "}
													<a
														href="https://discord.com/developers/applications"
														target="_blank"
														rel="noopener noreferrer"
														className="font-medium underline underline-offset-4"
													>
														https://discord.com/developers/applications
													</a>
													.
												</li>
												<li>Create a new application and add a bot to it.</li>
												<li>Copy the Bot Token from the Bot section.</li>
												<li>
													Invite the bot to your server with the following OAuth2 scopes and
													permissions:
													<ul className="list-disc pl-5 mt-1">
														<li>
															Scopes: <code>bot</code>
														</li>
														<li>
															Bot Permissions: <code>Read Messages/View Channels</code>,{" "}
															<code>Read Message History</code>, <code>Send Messages</code>
														</li>
													</ul>
												</li>
												<li>Paste the Bot Token above to connect.</li>
											</ol>
										</AccordionContent>
									</AccordionItem>

									<AccordionItem value="indexing">
										<AccordionTrigger className="text-lg font-medium">Indexing</AccordionTrigger>
										<AccordionContent className="space-y-4">
											<ol className="list-decimal pl-5 space-y-3">
												<li>
													Navigate to the Connector Dashboard and select the{" "}
													<strong>Discord</strong> Connector.
												</li>
												<li>
													Place the <strong>Bot Token</strong> under{" "}
													<strong>Step 1 Provide Credentials</strong>.
												</li>
												<li>
													Click <strong>Connect</strong> to establish the connection.
												</li>
											</ol>

											<Alert className="bg-muted">
												<Info className="h-4 w-4" />
												<AlertTitle>Important: Bot Channel Access</AlertTitle>
												<AlertDescription>
													After connecting, ensure the bot has access to all channels you want to
													index. You may need to adjust channel permissions in Discord.
												</AlertDescription>
											</Alert>

											<Alert className="bg-muted mt-4">
												<Info className="h-4 w-4" />
												<AlertTitle>First Indexing</AlertTitle>
												<AlertDescription>
													The first indexing pulls all accessible channels and may take longer than
													future updates. Only channels where the bot has access will be indexed.
												</AlertDescription>
											</Alert>

											<div className="mt-4">
												<h4 className="font-medium mb-2">Troubleshooting:</h4>
												<ul className="list-disc pl-5 space-y-2 text-muted-foreground">
													<li>
														<strong>Missing messages:</strong> If you don't see messages from a
														channel, check the bot's permissions for that channel.
													</li>
													<li>
														<strong>Bot not responding:</strong> Make sure the bot is online and the
														token is correct.
													</li>
													<li>
														<strong>Private channels:</strong> The bot must be explicitly granted
														access to private channels.
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
