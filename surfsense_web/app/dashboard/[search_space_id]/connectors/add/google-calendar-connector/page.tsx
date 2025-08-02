"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { IconCalendar } from "@tabler/icons-react";
import { motion } from "framer-motion";
import { ArrowLeft, Check, ExternalLink, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
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
import { useSearchSourceConnectors } from "@/hooks/useSearchSourceConnectors";

// Define the form schema with Zod
const googleCalendarConnectorFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	calendar_ids: z.array(z.string()).min(1, {
		message: "At least one calendar must be selected.",
	}),
});

// Define the type for the form values
type GoogleCalendarConnectorFormValues = z.infer<typeof googleCalendarConnectorFormSchema>;

// Interface for calendar data
interface Calendar {
	id: string;
	summary: string;
	description?: string;
	primary?: boolean;
	access_role: string;
	time_zone?: string;
}

// Interface for OAuth credentials
interface OAuthCredentials {
	client_id: string;
	client_secret: string;
	refresh_token: string;
	access_token: string;
}

export default function GoogleCalendarConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchParams = useSearchParams();
	const searchSpaceId = params.search_space_id as string;
	const isSuccess = searchParams.get("success") === "true";

	const { createConnector } = useSearchSourceConnectors();
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [isConnecting, setIsConnecting] = useState(false);
	const [isConnected, setIsConnected] = useState(false);
	const [calendars, setCalendars] = useState<Calendar[]>([]);
	const [credentials, setCredentials] = useState<OAuthCredentials | null>(null);

	// Initialize the form
	const form = useForm<GoogleCalendarConnectorFormValues>({
		resolver: zodResolver(googleCalendarConnectorFormSchema),
		defaultValues: {
			name: "",
			calendar_ids: [],
		},
	});

	useEffect(() => {
		if (isSuccess) {
			toast.success("Google Calendar connector created successfully!");
		}
	}, [isSuccess]);

	// Check for OAuth callback parameters
	useEffect(() => {
		const success = searchParams.get("success");
		const error = searchParams.get("error");
		const message = searchParams.get("message");
		const sessionKey = searchParams.get("session_key");

		if (success === "true" && sessionKey) {
			// Fetch OAuth data from backend
			fetchOAuthData(sessionKey);
		} else if (error) {
			toast.error(message || "Failed to connect to Google Calendar");
		}
	}, [searchParams]);

	// Fetch OAuth data from backend
	const fetchOAuthData = async (sessionKey: string) => {
		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/auth/google/session?session_key=${sessionKey}`,
				{
					method: "GET",
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
				}
			);

			if (!response.ok) {
				throw new Error("Failed to fetch OAuth data");
			}

			const data = await response.json();

			setCredentials(data.credentials);
			setCalendars(data.calendars);
			setIsConnected(true);
			toast.success("Successfully connected to Google Calendar!");
		} catch (error) {
			console.error("Error fetching OAuth data:", error);
			toast.error("Failed to retrieve Google Calendar data");
		}
	};

	// Handle Google OAuth connection
	const handleConnectGoogle = async () => {
		setIsConnecting(true);
		try {
			// Call backend to initiate OAuth flow
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/auth/google/calendar/connector/add/?space_id=${searchSpaceId}`,
				{
					method: "GET",
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
				}
			);

			if (!response.ok) {
				throw new Error("Failed to initiate Google OAuth");
			}

			const data = await response.json();

			// Redirect to Google for authentication
			window.location.href = data.auth_url;
		} catch (error) {
			console.error("Error connecting to Google:", error);
			toast.error("Failed to connect to Google Calendar");
			setIsConnecting(false);
		}
	};

	// Handle form submission
	const onSubmit = async (values: GoogleCalendarConnectorFormValues) => {
		if (!isConnected || !credentials) {
			toast.error("Please connect your Google account first");
			return;
		}

		if (values.calendar_ids.length === 0) {
			toast.error("Please select at least one calendar");
			return;
		}

		setIsSubmitting(true);
		try {
			await createConnector({
				name: values.name,
				connector_type: "GOOGLE_CALENDAR_CONNECTOR",
				config: {
					GOOGLE_CALENDAR_CLIENT_ID: credentials.client_id,
					GOOGLE_CALENDAR_CLIENT_SECRET: credentials.client_secret,
					GOOGLE_CALENDAR_REFRESH_TOKEN: credentials.refresh_token,
					GOOGLE_CALENDAR_CALENDAR_IDS: values.calendar_ids,
				},
				is_indexable: true,
				last_indexed_at: null,
			});

			toast.success("Google Calendar connector created successfully!");

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
		<div className="container mx-auto py-8 max-w-2xl">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
			>
				{/* Header */}
				<div className="mb-8">
					<Link
						href={`/dashboard/${searchSpaceId}/connectors/add`}
						className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
					>
						<ArrowLeft className="mr-2 h-4 w-4" />
						Back to connectors
					</Link>
					<div className="flex items-center gap-4">
						<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900">
							<IconCalendar className="h-6 w-6 text-blue-600 dark:text-blue-400" />
						</div>
						<div>
							<h1 className="text-3xl font-bold tracking-tight">Connect Google Calendar</h1>
							<p className="text-muted-foreground">
								Connect your Google Calendar to search events, meetings and schedules.
							</p>
						</div>
					</div>
				</div>

				{/* OAuth Connection Card */}
				{!isConnected ? (
					<Card>
						<CardHeader>
							<CardTitle>Connect Your Google Account</CardTitle>
							<CardDescription>
								Connect your Google account to access your calendar events. We'll only request
								read-only access to your calendars.
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<div className="flex items-center space-x-2 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>Read-only access to your calendar events</span>
							</div>
							<div className="flex items-center space-x-2 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>Access works even when you're offline</span>
							</div>
							<div className="flex items-center space-x-2 text-sm text-muted-foreground">
								<Check className="h-4 w-4 text-green-500" />
								<span>You can disconnect anytime</span>
							</div>
						</CardContent>
						<CardFooter className="flex justify-between">
							<Button
								type="button"
								variant="outline"
								onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/add`)}
							>
								Cancel
							</Button>
							<Button onClick={handleConnectGoogle} disabled={isConnecting}>
								{isConnecting ? (
									<>
										<Loader2 className="mr-2 h-4 w-4 animate-spin" />
										Connecting...
									</>
								) : (
									<>
										<ExternalLink className="mr-2 h-4 w-4" />
										Connect Your Google Account
									</>
								)}
							</Button>
						</CardFooter>
					</Card>
				) : (
					/* Configuration Form Card */
					<Card>
						<CardHeader>
							<CardTitle>Configure Google Calendar Connector</CardTitle>
							<CardDescription>
								Your Google account is connected! Now select which calendars to include and give
								your connector a name.
							</CardDescription>
						</CardHeader>
						<Form {...form}>
							<form onSubmit={form.handleSubmit(onSubmit)}>
								<CardContent className="space-y-6">
									{/* Connector Name */}
									<FormField
										control={form.control}
										name="name"
										render={({ field }) => (
											<FormItem>
												<FormLabel>Connector Name</FormLabel>
												<FormControl>
													<Input placeholder="My Google Calendar" {...field} />
												</FormControl>
												<FormDescription>
													A friendly name to identify this connector.
												</FormDescription>
												<FormMessage />
											</FormItem>
										)}
									/>

									{/* Calendar Selection */}
									<FormField
										control={form.control}
										name="calendar_ids"
										render={() => (
											<FormItem>
												<div className="mb-4">
													<FormLabel className="text-base">Select Calendars</FormLabel>
													<FormDescription>
														Choose which calendars you want to include in your search results.
													</FormDescription>
												</div>
												{calendars.map((calendar) => (
													<FormField
														key={calendar.id}
														control={form.control}
														name="calendar_ids"
														render={({ field }) => {
															return (
																<FormItem
																	key={calendar.id}
																	className="flex flex-row items-start space-x-3 space-y-0"
																>
																	<FormControl>
																		<Checkbox
																			checked={field.value?.includes(calendar.id)}
																			onCheckedChange={(checked) => {
																				return checked
																					? field.onChange([...field.value, calendar.id])
																					: field.onChange(
																							field.value?.filter((value) => value !== calendar.id)
																						);
																			}}
																		/>
																	</FormControl>
																	<div className="space-y-1 leading-none">
																		<FormLabel className="font-normal">
																			{calendar.summary}
																			{calendar.primary && (
																				<span className="ml-2 text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
																					Primary
																				</span>
																			)}
																		</FormLabel>
																		{calendar.description && (
																			<FormDescription className="text-xs">
																				{calendar.description}
																			</FormDescription>
																		)}
																	</div>
																</FormItem>
															);
														}}
													/>
												))}
												<FormMessage />
											</FormItem>
										)}
									/>
								</CardContent>
								<CardFooter className="flex justify-between">
									<Button
										type="button"
										variant="outline"
										onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/add`)}
									>
										Cancel
									</Button>
									<Button
										type="submit"
										disabled={isSubmitting || form.watch("calendar_ids").length === 0}
									>
										{isSubmitting ? (
											<>
												<Loader2 className="mr-2 h-4 w-4 animate-spin" />
												Creating...
											</>
										) : (
											<>
												<Check className="mr-2 h-4 w-4" />
												Create Connector
											</>
										)}
									</Button>
								</CardFooter>
							</form>
						</Form>
					</Card>
				)}

				{/* Help Section */}
				<Card className="mt-6">
					<CardHeader>
						<CardTitle className="text-lg">How It Works</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div>
							<h4 className="font-medium mb-2">1. Connect Your Account</h4>
							<p className="text-sm text-muted-foreground">
								Click "Connect Your Google Account" to start the secure OAuth process. You'll be
								redirected to Google to sign in.
							</p>
						</div>
						<div>
							<h4 className="font-medium mb-2">2. Grant Permissions</h4>
							<p className="text-sm text-muted-foreground">
								Google will ask for permission to read your calendar events. We only request
								read-only access to keep your data safe.
							</p>
						</div>
						<div>
							<h4 className="font-medium mb-2">3. Select Calendars</h4>
							<p className="text-sm text-muted-foreground">
								Choose which calendars you want to include in your search results. You can select
								multiple calendars.
							</p>
						</div>
						<div>
							<h4 className="font-medium mb-2">4. Start Searching</h4>
							<p className="text-sm text-muted-foreground">
								Once connected, your calendar events will be indexed and searchable alongside your
								other content.
							</p>
						</div>
						{isConnected && (
							<div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
								<p className="text-sm text-green-800">
									✅ Your Google account is successfully connected! You can now configure your
									connector above.
								</p>
							</div>
						)}
					</CardContent>
				</Card>
			</motion.div>
		</div>
	);
}
