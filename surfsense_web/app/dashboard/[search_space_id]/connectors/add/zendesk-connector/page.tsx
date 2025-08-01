"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "framer-motion";
import { ArrowLeft, Check, Info, Loader2 } from "lucide-react";
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
import { useSearchSourceConnectors } from "@/hooks/useSearchSourceConnectors";

// Define the form schema with Zod
const zendeskConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	subdomain: z.string().min(3, { message: "Subdomain must be at least 3 characters." }),
	email: z.string().email({ message: "Invalid email address." }),
	api_token: z.string().min(20, { message: "API token appears to be too short." }),
});

// Define the type for the form values
type ZendeskConnectorFormValues = z.infer<typeof zendeskConnectorFormSchema>;

export default function ZendeskConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form
	const form = useForm<ZendeskConnectorFormValues>({
		resolver: zodResolver(zendeskConnectorFormSchema),
		defaultValues: {
			name: "Zendesk Connector",
			subdomain: "",
			email: "",
			api_token: "",
		},
	});

	// Handle form submission
	const onSubmit = async (values: ZendeskConnectorFormValues) => {
		setIsSubmitting(true);
		try {
			await createConnector({
				name: values.name,
				connector_type: "ZENDESK_CONNECTOR",
				config: {
					ZENDESK_SUBDOMAIN: values.subdomain,
					ZENDESK_EMAIL: values.email,
					ZENDESK_API_TOKEN: values.api_token,
				},
				is_indexable: true,
				last_indexed_at: null,
			});

			toast.success("Zendesk connector created successfully!");
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
								<CardTitle className="text-2xl font-bold">Connect Zendesk</CardTitle>
								<CardDescription>
									Integrate with Zendesk to search and retrieve information from your support
									tickets.
								</CardDescription>
							</CardHeader>
							<CardContent>
								<Alert className="mb-6 bg-muted">
									<Info className="h-4 w-4" />
									<AlertTitle>API Token Required</AlertTitle>
									<AlertDescription>
										You'll need a Zendesk API Token to use this connector. You can generate one from
										your Zendesk admin settings.
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
														<Input placeholder="My Zendesk Connector" {...field} />
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
											name="subdomain"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Zendesk Subdomain</FormLabel>
													<FormControl>
														<Input placeholder="your-company" {...field} />
													</FormControl>
													<FormDescription>
														Your Zendesk subdomain (e.g., 'your-company' in
														'your-company.zendesk.com').
													</FormDescription>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={form.control}
											name="email"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Zendesk Email</FormLabel>
													<FormControl>
														<Input type="email" placeholder="your-email@example.com" {...field} />
													</FormControl>
													<FormDescription>
														The email address you use to log in to Zendesk.
													</FormDescription>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={form.control}
											name="api_token"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Zendesk API Token</FormLabel>
													<FormControl>
														<Input type="password" placeholder="API Token..." {...field} />
													</FormControl>
													<FormDescription>
														Your Zendesk API Token will be encrypted and stored securely.
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
														Connect Zendesk
													</>
												)}
											</Button>
										</div>
									</form>
								</Form>
							</CardContent>
							<CardFooter className="flex flex-col items-start border-t bg-muted/50 px-6 py-4">
								<h4 className="text-sm font-medium">What you get with Zendesk integration:</h4>
								<ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
									<li>Search through your Zendesk tickets</li>
									<li>Access historical ticket data</li>
									<li>Connect your customer support knowledge directly to your search space</li>
								</ul>
							</CardFooter>
						</Card>
					</TabsContent>

					<TabsContent value="documentation">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold">
									Zendesk Connector Documentation
								</CardTitle>
								<CardDescription>
									Learn how to set up and use the Zendesk connector to index your ticket data.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<div>
									<h3 className="text-xl font-semibold mb-2">How it works</h3>
									<p className="text-muted-foreground">
										The Zendesk connector indexes all tickets from your Zendesk account.
									</p>
								</div>

								<Accordion type="single" collapsible className="w-full">
									<AccordionItem value="authorization">
										<AccordionTrigger className="text-lg font-medium">
											Authorization
										</AccordionTrigger>
										<AccordionContent className="space-y-4">
											<Alert className="bg-muted">
												<Info className="h-4 w-4" />
												<AlertTitle>API Token Required</AlertTitle>
												<AlertDescription>
													You must generate an API token from your Zendesk admin settings.
												</AlertDescription>
											</Alert>

											<ol className="list-decimal pl-5 space-y-3">
												<li>Go to your Zendesk Admin Center.</li>
												<li>Navigate to Apps and integrations &gt; APIs &gt; Zendesk API.</li>
												<li>Enable Token Access and create a new API token.</li>
												<li>Copy the API token and paste it above.</li>
											</ol>
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
