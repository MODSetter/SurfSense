"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "framer-motion";
import { ArrowLeft, Check, CircleAlert, Info, ListChecks, Loader2, Trello } from "lucide-react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useSearchSourceConnectors } from "@/hooks/useSearchSourceConnectors";
import { TrelloBoard } from "@/components/editConnector/types";

const trelloCredentialsSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	trello_api_key: z.string().min(1, "API Key is required."),
	trello_api_token: z.string().min(1, "Token is required."),
});

type TrelloFormValues = z.infer<typeof trelloCredentialsSchema>;

export default function TrelloConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [step, setStep] = useState<"enter_credentials" | "select_boards">("enter_credentials");
	const [isFetchingBoards, setIsFetchingBoards] = useState(false);
	const [isCreatingConnector, setIsCreatingConnector] = useState(false);
	const [boards, setBoards] = useState<TrelloBoard[]>([]);
	const [selectedBoards, setSelectedBoards] = useState<string[]>([]);
	const [connectorName, setConnectorName] = useState<string>("Trello Connector");
	const [validatedApiKey, setValidatedApiKey] = useState<string>("");
	const [validatedApiToken, setValidatedApiToken] = useState<string>("");

	const { createConnector } = useSearchSourceConnectors();

	const form = useForm<TrelloFormValues>({
		resolver: zodResolver(trelloCredentialsSchema),
		defaultValues: {
			name: connectorName,
			trello_api_key: "",
			trello_api_token: "",
		},
	});

	const fetchBoards = async (values: TrelloFormValues) => {
		setIsFetchingBoards(true);
		setConnectorName(values.name);
		setValidatedApiKey(values.trello_api_key);
		setValidatedApiToken(values.trello_api_token);
		try {
			const token = localStorage.getItem("surfsense_bearer_token");
			if (!token) {
				throw new Error("No authentication token found");
			}

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/trello/boards/`,
				{
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify({ trello_api_key: values.trello_api_key, trello_api_token: values.trello_api_token }),
				}
			);

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || `Failed to fetch boards: ${response.statusText}`);
			}

			const data: TrelloBoard[] = await response.json();
			setBoards(data);
			setStep("select_boards");
			toast.success(`Found ${data.length} boards.`);
		} catch (error) {
			console.error("Error fetching Trello boards:", error);
			const errorMessage =
				error instanceof Error
					? error.message
					: "Failed to fetch boards. Please check the credentials and try again.";
			toast.error(errorMessage);
		} finally {
			setIsFetchingBoards(false);
		}
	};

	const handleCreateConnector = async () => {
		if (selectedBoards.length === 0) {
			toast.warning("Please select at least one board to index.");
			return;
		}

		setIsCreatingConnector(true);
		try {
			await createConnector({
				name: connectorName,
				connector_type: "TRELLO_CONNECTOR",
				config: {
					TRELLO_API_KEY: validatedApiKey,
					TRELLO_API_TOKEN: validatedApiToken,
					board_ids: selectedBoards,
				},
				is_indexable: true,
				last_indexed_at: null,
			});

			toast.success("Trello connector created successfully!");
			router.push(`/dashboard/${searchSpaceId}/connectors`);
		} catch (error) {
			console.error("Error creating Trello connector:", error);
			const errorMessage =
				error instanceof Error ? error.message : "Failed to create Trello connector.";
			toast.error(errorMessage);
		} finally {
			setIsCreatingConnector(false);
		}
	};

	const handleBoardSelection = (boardId: string, checked: boolean) => {
		setSelectedBoards((prev) =>
			checked ? [...prev, boardId] : prev.filter((id) => id !== boardId)
		);
	};

	return (
		<div className="container mx-auto py-8 max-w-3xl">
			<Button
				variant="ghost"
				className="mb-6"
				onClick={() => {
					if (step === "select_boards") {
						setStep("enter_credentials");
						setBoards([]);
						setSelectedBoards([]);
						setValidatedApiKey("");
						setValidatedApiToken("");
						form.reset({ name: connectorName, trello_api_key: "", trello_api_token: "" });
					} else {
						router.push(`/dashboard/${searchSpaceId}/connectors/add`);
					}
				}}
			>
				<ArrowLeft className="mr-2 h-4 w-4" />
				{step === "select_boards" ? "Back to Credentials" : "Back to Add Connectors"}
			</Button>

			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
			>
				<Tabs defaultValue="connect" className="w-full">
					<TabsList className="grid w-full grid-cols-2 mb-6">
						<TabsTrigger value="connect">Connect Trello</TabsTrigger>
						<TabsTrigger value="documentation">Setup Guide</TabsTrigger>
					</TabsList>

					<TabsContent value="connect">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold flex items-center gap-2">
									{step === "enter_credentials" ? (
										<Trello className="h-6 w-6" />
									) : (
										<ListChecks className="h-6 w-6" />
									)}
									{step === "enter_credentials" ? "Connect Trello Account" : "Select Boards to Index"}
								</CardTitle>
								<CardDescription>
									{step === "enter_credentials"
										? "Provide a name and Trello API credentials to fetch accessible boards."
										: `Select which boards you want SurfSense to index for search. Found ${boards.length} boards.`}
								</CardDescription>
							</CardHeader>

							<Form {...form}>
								{step === "enter_credentials" && (
									<CardContent>
										<Alert className="mb-6 bg-muted">
											<Info className="h-4 w-4" />
											<AlertTitle>Trello API Credentials Required</AlertTitle>
											<AlertDescription>
												You'll need a Trello API Key and Token. You can get them from{" "}
												<a
													href="https://trello.com/power-ups/admin"
													target="_blank"
													rel="noopener noreferrer"
													className="font-medium underline underline-offset-4"
												>
													Trello Power-Ups Admin
												</a>
												.
											</AlertDescription>
										</Alert>

										<form onSubmit={form.handleSubmit(fetchBoards)} className="space-y-6">
											<FormField
												control={form.control}
												name="name"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Connector Name</FormLabel>
														<FormControl>
															<Input placeholder="My Trello Connector" {...field} />
														</FormControl>
														<FormDescription>
															A friendly name to identify this Trello connection.
														</FormDescription>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={form.control}
												name="trello_api_key"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Trello API Key</FormLabel>
														<FormControl>
															<Input
																placeholder="Your Trello API Key"
																{...field}
															/>
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={form.control}
												name="trello_api_token"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Trello API Token</FormLabel>
														<FormControl>
															<Input
																type="password"
																placeholder="Your Trello API Token"
																{...field}
															/>
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											<div className="flex justify-end">
												<Button
													type="submit"
													disabled={isFetchingBoards}
													className="w-full sm:w-auto"
												>
													{isFetchingBoards ? (
														<>
															<Loader2 className="mr-2 h-4 w-4 animate-spin" />
															Fetching Boards...
														</>
													) : (
														"Fetch Boards"
													)}
												</Button>
											</div>
										</form>
									</CardContent>
								)}

								{step === "select_boards" && (
									<CardContent>
										{boards.length === 0 ? (
											<Alert variant="destructive">
												<CircleAlert className="h-4 w-4" />
												<AlertTitle>No Boards Found</AlertTitle>
												<AlertDescription>
													No boards were found. Please check your credentials and try again.
												</AlertDescription>
											</Alert>
										) : (
											<div className="space-y-4">
												<FormLabel>Boards ({selectedBoards.length} selected)</FormLabel>
												<div className="h-64 w-full rounded-md border p-4 overflow-y-auto">
													{boards.map((board) => (
														<div key={board.id} className="flex items-center space-x-2 mb-2 py-1">
															<Checkbox
																id={`board-${board.id}`}
																checked={selectedBoards.includes(board.id)}
																onCheckedChange={(checked) =>
																	handleBoardSelection(board.id, !!checked)
																}
															/>
															<label
																htmlFor={`board-${board.id}`}
																className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
															>
																{board.name}
															</label>
														</div>
													))}
												</div>
												<FormDescription>
													Select the boards you wish to index.
												</FormDescription>

												<div className="flex justify-between items-center pt-4">
													<Button
														variant="outline"
														onClick={() => {
															setStep("enter_credentials");
															setBoards([]);
															setSelectedBoards([]);
															setValidatedApiKey("");
															setValidatedApiToken("");
															form.reset({ name: connectorName, trello_api_key: "", trello_api_token: "" });
														}}
													>
														Back
													</Button>
													<Button
														onClick={handleCreateConnector}
														disabled={isCreatingConnector || selectedBoards.length === 0}
														className="w-full sm:w-auto"
													>
														{isCreatingConnector ? (
															<>
																<Loader2 className="mr-2 h-4 w-4 animate-spin" />
																Creating Connector...
															</>
														) : (
															<>
																<Check className="mr-2 h-4 w-4" />
																Create Connector
															</>
														)}
													</Button>
												</div>
											</div>
										)}
									</CardContent>
								)}
							</Form>

							<CardFooter className="flex flex-col items-start border-t bg-muted/50 px-6 py-4">
								<h4 className="text-sm font-medium">What you get with Trello integration:</h4>
								<ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
									<li>Search through cards in your selected boards</li>
									<li>Access card descriptions and comments</li>
									<li>Connect your project management data directly to your search space</li>
								</ul>
							</CardFooter>
						</Card>
					</TabsContent>

					<TabsContent value="documentation">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold">Trello Connector Setup Guide</CardTitle>
								<CardDescription>
									Learn how to get your Trello API Key and Token.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<Accordion type="single" collapsible className="w-full">
									<AccordionItem value="create_credentials">
										<AccordionTrigger className="text-lg font-medium">
											Step 1: Get API Credentials
										</AccordionTrigger>
										<AccordionContent>
											<div className="space-y-6">
												<div>
													<ol className="list-decimal pl-5 space-y-3">
														<li>
															Go to{" "}
															<a
																href="https://trello.com/power-ups/admin"
																target="_blank"
																rel="noopener noreferrer"
																className="font-medium underline underline-offset-4"
															>
																Trello Power-Ups Admin
															</a>
															.
														</li>
														<li>
															Click on "New" to create a new Power-Up.
														</li>
														<li>
                                                            You will find your API key in the next page.
														</li>
														<li>
															You can generate a Token by clicking on the "Token" link.
														</li>
														<li>
															Copy both the API Key and the Token.
														</li>
													</ol>
												</div>
											</div>
										</AccordionContent>
									</AccordionItem>

									<AccordionItem value="connect_app">
										<AccordionTrigger className="text-lg font-medium">
											Step 2: Connect in SurfSense
										</AccordionTrigger>
										<AccordionContent className="space-y-4">
											<ol className="list-decimal pl-5 space-y-3">
												<li>Navigate to the "Connect Trello" tab.</li>
												<li>Enter a name for your connector.</li>
												<li>
													Paste the copied API Key and Token into the respective fields.
												</li>
												<li>
													Click <strong>Fetch Boards</strong>.
												</li>
												<li>
													Select the boards you want to index.
												</li>
												<li>
													Click <strong>Create Connector</strong>.
												</li>
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
