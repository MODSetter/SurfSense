"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Check, CircleAlert, Github, Info, ListChecks, Loader2 } from "lucide-react";
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
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
// Assuming useSearchSourceConnectors hook exists and works similarly
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";

// Define the form schema with Zod for GitHub PAT entry step
const githubPatFormSchema = z.object({
	name: z.string().min(3, {
		message: "Connector name must be at least 3 characters.",
	}),
	github_pat: z
		.string()
		.min(20, {
			// Apply min length first
			message: "GitHub Personal Access Token seems too short.",
		})
		.refine((pat) => pat.startsWith("ghp_") || pat.startsWith("github_pat_"), {
			// Then refine the pattern
			message: "GitHub PAT should start with 'ghp_' or 'github_pat_'",
		}),
});

// Define the type for the form values
type GithubPatFormValues = z.infer<typeof githubPatFormSchema>;

// Type for fetched GitHub repositories
interface GithubRepo {
	id: number;
	name: string;
	full_name: string;
	private: boolean;
	url: string;
	description: string | null;
	last_updated: string | null;
}

export default function GithubConnectorPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = params.search_space_id as string;
	const [step, setStep] = useState<"enter_pat" | "select_repos">("enter_pat");
	const [isFetchingRepos, setIsFetchingRepos] = useState(false);
	const [isCreatingConnector, setIsCreatingConnector] = useState(false);
	const [repositories, setRepositories] = useState<GithubRepo[]>([]);
	const [selectedRepos, setSelectedRepos] = useState<string[]>([]);
	const [connectorName, setConnectorName] = useState<string>("GitHub Connector");
	const [validatedPat, setValidatedPat] = useState<string>(""); // Store the validated PAT

	const { createConnector } = useSearchSourceConnectors();

	// Initialize the form for PAT entry
	const form = useForm<GithubPatFormValues>({
		resolver: zodResolver(githubPatFormSchema),
		defaultValues: {
			name: connectorName,
			github_pat: "",
		},
	});

	// Function to fetch repositories using the new backend endpoint
	const fetchRepositories = async (values: GithubPatFormValues) => {
		setIsFetchingRepos(true);
		setConnectorName(values.name); // Store the name
		setValidatedPat(values.github_pat); // Store the PAT temporarily
		try {
			const token = localStorage.getItem("surfsense_bearer_token");
			if (!token) {
				throw new Error("No authentication token found");
			}

			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/github/repositories`,
				{
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify({ github_pat: values.github_pat }),
				}
			);

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.detail || `Failed to fetch repositories: ${response.statusText}`);
			}

			const data: GithubRepo[] = await response.json();
			setRepositories(data);
			setStep("select_repos"); // Move to the next step
			toast.success(`Found ${data.length} repositories.`);
		} catch (error) {
			console.error("Error fetching GitHub repositories:", error);
			const errorMessage =
				error instanceof Error
					? error.message
					: "Failed to fetch repositories. Please check the PAT and try again.";
			toast.error(errorMessage);
		} finally {
			setIsFetchingRepos(false);
		}
	};

	// Handle final connector creation
	const handleCreateConnector = async () => {
		if (selectedRepos.length === 0) {
			toast.warning("Please select at least one repository to index.");
			return;
		}

		setIsCreatingConnector(true);
		try {
			await createConnector(
				{
					name: connectorName, // Use the stored name
					connector_type: EnumConnectorName.GITHUB_CONNECTOR,
					config: {
						GITHUB_PAT: validatedPat, // Use the stored validated PAT
						repo_full_names: selectedRepos, // Add the selected repo names
					},
					is_indexable: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				parseInt(searchSpaceId)
			);

			toast.success("GitHub connector created successfully!");
			router.push(`/dashboard/${searchSpaceId}/connectors`);
		} catch (error) {
			console.error("Error creating GitHub connector:", error);
			const errorMessage =
				error instanceof Error ? error.message : "Failed to create GitHub connector.";
			toast.error(errorMessage);
		} finally {
			setIsCreatingConnector(false);
		}
	};

	// Handle checkbox changes
	const handleRepoSelection = (repoFullName: string, checked: boolean) => {
		setSelectedRepos((prev) =>
			checked ? [...prev, repoFullName] : prev.filter((name) => name !== repoFullName)
		);
	};

	return (
		<div className="container mx-auto py-8 max-w-3xl">
			<Button
				variant="ghost"
				className="mb-6"
				onClick={() => {
					if (step === "select_repos") {
						// Go back to PAT entry, clear sensitive/fetched data
						setStep("enter_pat");
						setRepositories([]);
						setSelectedRepos([]);
						setValidatedPat("");
						// Reset form PAT field, keep name
						form.reset({ name: connectorName, github_pat: "" });
					} else {
						router.push(`/dashboard/${searchSpaceId}/connectors/add`);
					}
				}}
			>
				<ArrowLeft className="mr-2 h-4 w-4" />
				{step === "select_repos" ? "Back to PAT Entry" : "Back to Add Connectors"}
			</Button>

			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
			>
				<Tabs defaultValue="connect" className="w-full">
					<TabsList className="grid w-full grid-cols-2 mb-6">
						<TabsTrigger value="connect">Connect GitHub</TabsTrigger>
						<TabsTrigger value="documentation">Setup Guide</TabsTrigger>
					</TabsList>

					<TabsContent value="connect">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold flex items-center gap-2">
									{step === "enter_pat" ? (
										getConnectorIcon(EnumConnectorName.GITHUB_CONNECTOR, "h-6 w-6")
									) : (
										<ListChecks className="h-6 w-6" />
									)}
									{step === "enter_pat" ? "Connect GitHub Account" : "Select Repositories to Index"}
								</CardTitle>
								<CardDescription>
									{step === "enter_pat"
										? "Provide a name and GitHub Personal Access Token (PAT) to fetch accessible repositories."
										: `Select which repositories you want SurfSense to index for search. Found ${repositories.length} repositories accessible via your PAT.`}
								</CardDescription>
							</CardHeader>

							<Form {...form}>
								{step === "enter_pat" && (
									<CardContent>
										<Alert className="mb-6 bg-muted">
											<Info className="h-4 w-4" />
											<AlertTitle>GitHub Personal Access Token (PAT) Required</AlertTitle>
											<AlertDescription>
												You'll need a GitHub PAT with the appropriate scopes (e.g., 'repo') to fetch
												repositories. You can create one from your{" "}
												<a
													href="https://github.com/settings/personal-access-tokens"
													target="_blank"
													rel="noopener noreferrer"
													className="font-medium underline underline-offset-4"
												>
													GitHub Developer Settings
												</a>
												. The PAT will be used to fetch repositories and then stored securely to
												enable indexing.
											</AlertDescription>
										</Alert>

										<form onSubmit={form.handleSubmit(fetchRepositories)} className="space-y-6">
											<FormField
												control={form.control}
												name="name"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Connector Name</FormLabel>
														<FormControl>
															<Input placeholder="My GitHub Connector" {...field} />
														</FormControl>
														<FormDescription>
															A friendly name to identify this GitHub connection.
														</FormDescription>
														<FormMessage />
													</FormItem>
												)}
											/>

											<FormField
												control={form.control}
												name="github_pat"
												render={({ field }) => (
													<FormItem>
														<FormLabel>GitHub Personal Access Token (PAT)</FormLabel>
														<FormControl>
															<Input
																type="password"
																placeholder="ghp_... or github_pat_..."
																{...field}
															/>
														</FormControl>
														<FormDescription>
															Enter your GitHub PAT here to fetch your repositories. It will be
															stored encrypted later.
														</FormDescription>
														<FormMessage />
													</FormItem>
												)}
											/>

											<div className="flex justify-end">
												<Button
													type="submit"
													disabled={isFetchingRepos}
													className="w-full sm:w-auto"
												>
													{isFetchingRepos ? (
														<>
															<Loader2 className="mr-2 h-4 w-4 animate-spin" />
															Fetching Repositories...
														</>
													) : (
														"Fetch Repositories"
													)}
												</Button>
											</div>
										</form>
									</CardContent>
								)}

								{step === "select_repos" && (
									<CardContent>
										{repositories.length === 0 ? (
											<Alert variant="destructive">
												<CircleAlert className="h-4 w-4" />
												<AlertTitle>No Repositories Found</AlertTitle>
												<AlertDescription>
													No repositories were found or accessible with the provided PAT. Please
													check the token and its permissions, then go back and try again.
												</AlertDescription>
											</Alert>
										) : (
											<div className="space-y-4">
												<FormLabel>Repositories ({selectedRepos.length} selected)</FormLabel>
												<div className="h-64 w-full rounded-md border p-4 overflow-y-auto">
													{repositories.map((repo) => (
														<div key={repo.id} className="flex items-center space-x-2 mb-2 py-1">
															<Checkbox
																id={`repo-${repo.id}`}
																checked={selectedRepos.includes(repo.full_name)}
																onCheckedChange={(checked) =>
																	handleRepoSelection(repo.full_name, !!checked)
																}
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
												<FormDescription>
													Select the repositories you wish to index. Only checked repositories will
													be processed.
												</FormDescription>

												<div className="flex justify-between items-center pt-4">
													<Button
														variant="outline"
														onClick={() => {
															setStep("enter_pat");
															setRepositories([]);
															setSelectedRepos([]);
															setValidatedPat("");
															form.reset({ name: connectorName, github_pat: "" });
														}}
													>
														Back
													</Button>
													<Button
														onClick={handleCreateConnector}
														disabled={isCreatingConnector || selectedRepos.length === 0}
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
								<h4 className="text-sm font-medium">What you get with GitHub integration:</h4>
								<ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
									<li>Search through code and documentation in your selected repositories</li>
									<li>Access READMEs, Markdown files, and common code files</li>
									<li>Connect your project knowledge directly to your search space</li>
									<li>Index your selected repositories for enhanced search capabilities</li>
								</ul>
							</CardFooter>
						</Card>
					</TabsContent>

					<TabsContent value="documentation">
						<Card className="border-2 border-border">
							<CardHeader>
								<CardTitle className="text-2xl font-bold">GitHub Connector Setup Guide</CardTitle>
								<CardDescription>
									Learn how to generate a Personal Access Token (PAT) and connect your GitHub
									account.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<div>
									<h3 className="text-xl font-semibold mb-2">How it works</h3>
									<p className="text-muted-foreground">
										The GitHub connector uses a Personal Access Token (PAT) to authenticate with the
										GitHub API. First, it fetches a list of repositories accessible to the token.
										You then select which repositories you want to index. The connector indexes
										relevant files (code, markdown, text) from only the selected repositories.
									</p>
									<ul className="mt-2 list-disc pl-5 text-muted-foreground">
										<li>
											The connector indexes files based on common code and documentation extensions.
										</li>
										<li>Large files (over 1MB) are skipped during indexing.</li>
										<li>Only selected repositories are indexed.</li>
										<li>
											Indexing runs periodically (check connector settings for frequency) to keep
											content up-to-date.
										</li>
									</ul>
								</div>

								<Accordion type="single" collapsible className="w-full">
									<AccordionItem value="create_pat">
										<AccordionTrigger className="text-lg font-medium">
											Step 1: Generate GitHub PAT
										</AccordionTrigger>
										<AccordionContent>
											<div className="space-y-6">
												<div>
													<h4 className="font-medium mb-2">Generating a Token:</h4>
													<ol className="list-decimal pl-5 space-y-3">
														<li>
															Go to your GitHub{" "}
															<a
																href="https://github.com/settings/tokens"
																target="_blank"
																rel="noopener noreferrer"
																className="font-medium underline underline-offset-4"
															>
																Developer settings
															</a>
															.
														</li>
														<li>
															Click on <strong>Personal access tokens</strong>, then choose{" "}
															<strong>Tokens (classic)</strong> or{" "}
															<strong>Fine-grained tokens</strong> (recommended if available and
															suitable).
														</li>
														<li>
															Click <strong>Generate new token</strong> (and choose the appropriate
															type).
														</li>
														<li>
															Give your token a descriptive name (e.g., "SurfSense Connector").
														</li>
														<li>
															Set an expiration date for the token (recommended for security).
														</li>
														<li>
															Under <strong>Select scopes</strong> (for classic tokens) or{" "}
															<strong>Repository access</strong> (for fine-grained), grant the
															necessary permissions. At minimum, the <strong>`repo`</strong> scope
															(or equivalent read access to repositories for fine-grained tokens) is
															required to read repository content.
														</li>
														<li>
															Click <strong>Generate token</strong>.
														</li>
														<li>
															<strong>Important:</strong> Copy your new PAT immediately. You won't
															be able to see it again after leaving the page.
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
												<li>Navigate to the "Connect GitHub" tab.</li>
												<li>Enter a name for your connector.</li>
												<li>
													Paste the copied GitHub PAT into the "GitHub Personal Access Token (PAT)"
													field.
												</li>
												<li>
													Click <strong>Fetch Repositories</strong>.
												</li>
												<li>
													If the PAT is valid, you'll see a list of your accessible repositories.
												</li>
												<li>
													Select the repositories you want SurfSense to index using the checkboxes.
												</li>
												<li>
													Click the <strong>Create Connector</strong> button.
												</li>
												<li>
													If the connection is successful, you will be redirected and can start
													indexing from the Connectors page.
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
