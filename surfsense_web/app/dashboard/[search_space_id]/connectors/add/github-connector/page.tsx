"use client";

import { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { motion } from "framer-motion";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { toast } from "sonner";
import { ArrowLeft, Check, Info, Loader2, Github } from "lucide-react";

// Assuming useSearchSourceConnectors hook exists and works similarly
import { useSearchSourceConnectors } from "@/hooks/useSearchSourceConnectors";
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
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Define the form schema with Zod for GitHub
const githubConnectorFormSchema = z.object({
    name: z.string().min(3, {
        message: "Connector name must be at least 3 characters.",
    }),
    github_pat: z.string()
        .min(20, { // Apply min length first
            message: "GitHub Personal Access Token seems too short.",
        })
        .refine(pat => pat.startsWith('ghp_') || pat.startsWith('github_pat_'), { // Then refine the pattern
            message: "GitHub PAT should start with 'ghp_' or 'github_pat_'",
        }),
});

// Define the type for the form values
type GithubConnectorFormValues = z.infer<typeof githubConnectorFormSchema>;

export default function GithubConnectorPage() {
    const router = useRouter();
    const params = useParams();
    const searchSpaceId = params.search_space_id as string;
    const [isSubmitting, setIsSubmitting] = useState(false);
    const { createConnector } = useSearchSourceConnectors(); // Assuming this hook exists

    // Initialize the form
    const form = useForm<GithubConnectorFormValues>({
        resolver: zodResolver(githubConnectorFormSchema),
        defaultValues: {
            name: "GitHub Connector",
            github_pat: "",
        },
    });

    // Handle form submission
    const onSubmit = async (values: GithubConnectorFormValues) => {
        setIsSubmitting(true);
        try {
            await createConnector({
                name: values.name,
                connector_type: "GITHUB_CONNECTOR",
                config: {
                    GITHUB_PAT: values.github_pat,
                },
                is_indexable: true, // GitHub connector is indexable
                last_indexed_at: null, // New connector hasn't been indexed
            });

            toast.success("GitHub connector created successfully!");

            // Navigate back to connectors management page (or the add page)
            router.push(`/dashboard/${searchSpaceId}/connectors`);
        } catch (error) { // Added type check for error
            console.error("Error creating GitHub connector:", error);
            // Display specific backend error message if available
            const errorMessage = error instanceof Error ? error.message : "Failed to create GitHub connector. Please check the PAT and permissions.";
            toast.error(errorMessage);
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
                Back to Add Connectors
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
                                <CardTitle className="text-2xl font-bold flex items-center gap-2"><Github className="h-6 w-6" /> Connect GitHub Account</CardTitle>
                                <CardDescription>
                                    Integrate with GitHub using a Personal Access Token (PAT) to search and retrieve information from accessible repositories. This connector can index your code and documentation.
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <Alert className="mb-6 bg-muted">
                                    <Info className="h-4 w-4" />
                                    <AlertTitle>GitHub Personal Access Token (PAT) Required</AlertTitle>
                                    <AlertDescription>
                                        You'll need a GitHub PAT with the appropriate scopes (e.g., 'repo') to use this connector. You can create one from your
                                        <a
                                            href="https://github.com/settings/personal-access-tokens"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="font-medium underline underline-offset-4 ml-1"
                                        >
                                            GitHub Developer Settings
                                        </a>.
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
                                                        Your GitHub PAT will be encrypted and stored securely. Ensure it has the necessary 'repo' scopes.
                                                    </FormDescription>
                                                    <FormMessage />
                                                </FormItem>
                                            )}
                                        />

                                        <div className="flex justify-end">
                                            <Button
                                                type="submit"
                                                disabled={isSubmitting}
                                                className="w-full sm:w-auto"
                                            >
                                                {isSubmitting ? (
                                                    <>
                                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                        Connecting...
                                                    </>
                                                ) : (
                                                    <>
                                                        <Check className="mr-2 h-4 w-4" />
                                                        Connect GitHub
                                                    </>
                                                )}
                                            </Button>
                                        </div>
                                    </form>
                                </Form>
                            </CardContent>
                            <CardFooter className="flex flex-col items-start border-t bg-muted/50 px-6 py-4">
                                <h4 className="text-sm font-medium">What you get with GitHub integration:</h4>
                                <ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
                                    <li>Search through code and documentation in your repositories</li>
                                    <li>Access READMEs, Markdown files, and common code files</li>
                                    <li>Connect your project knowledge directly to your search space</li>
                                    <li>Index your repositories for enhanced search capabilities</li>
                                </ul>
                            </CardFooter>
                        </Card>
                    </TabsContent>

                    <TabsContent value="documentation">
                        <Card className="border-2 border-border">
                            <CardHeader>
                                <CardTitle className="text-2xl font-bold">GitHub Connector Setup Guide</CardTitle>
                                <CardDescription>
                                    Learn how to generate a Personal Access Token (PAT) and connect your GitHub account.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div>
                                    <h3 className="text-xl font-semibold mb-2">How it works</h3>
                                    <p className="text-muted-foreground">
                                        The GitHub connector uses a Personal Access Token (PAT) to authenticate with the GitHub API. It fetches information about repositories accessible to the token and indexes relevant files (code, markdown, text).
                                    </p>
                                    <ul className="mt-2 list-disc pl-5 text-muted-foreground">
                                        <li>The connector indexes files based on common code and documentation extensions.</li>
                                        <li>Large files (over 1MB) are skipped during indexing.</li>
                                        <li>Indexing runs periodically (check connector settings for frequency) to keep content up-to-date.</li>
                                    </ul>
                                </div>

                                <Accordion type="single" collapsible className="w-full">
                                    <AccordionItem value="create_pat">
                                        <AccordionTrigger className="text-lg font-medium">Step 1: Create a GitHub PAT</AccordionTrigger>
                                        <AccordionContent className="space-y-4">
                                            <Alert className="bg-muted">
                                                <Info className="h-4 w-4" />
                                                <AlertTitle>Token Security</AlertTitle>
                                                <AlertDescription>
                                                    Treat your PAT like a password. Store it securely and consider using fine-grained tokens if possible.
                                                </AlertDescription>
                                            </Alert>

                                            <div className="space-y-6">
                                                <div>
                                                    <h4 className="font-medium mb-2">Generating a Token:</h4>
                                                    <ol className="list-decimal pl-5 space-y-3">
                                                        <li>Go to your GitHub <a href="https://github.com/settings/tokens" target="_blank" rel="noopener noreferrer" className="font-medium underline underline-offset-4">Developer settings</a>.</li>
                                                        <li>Click on <strong>Personal access tokens</strong>, then choose <strong>Tokens (classic)</strong> or <strong>Fine-grained tokens</strong> (recommended if available and suitable).</li>
                                                        <li>Click <strong>Generate new token</strong> (and choose the appropriate type).</li>
                                                        <li>Give your token a descriptive name (e.g., "SurfSense Connector").</li>
                                                        <li>Set an expiration date for the token (recommended for security).</li>
                                                        <li>Under <strong>Select scopes</strong> (for classic tokens) or <strong>Repository access</strong> (for fine-grained), grant the necessary permissions. At minimum, the <strong>`repo`</strong> scope (or equivalent read access to repositories for fine-grained tokens) is required to read repository content.</li>
                                                        <li>Click <strong>Generate token</strong>.</li>
                                                        <li><strong>Important:</strong> Copy your new PAT immediately. You won't be able to see it again after leaving the page.</li>
                                                    </ol>
                                                </div>
                                            </div>
                                        </AccordionContent>
                                    </AccordionItem>

                                    <AccordionItem value="connect_app">
                                        <AccordionTrigger className="text-lg font-medium">Step 2: Connect in SurfSense</AccordionTrigger>
                                        <AccordionContent className="space-y-4">
                                            <ol className="list-decimal pl-5 space-y-3">
                                                <li>Paste the copied GitHub PAT into the "GitHub Personal Access Token (PAT)" field on the "Connect GitHub" tab.</li>
                                                <li>Optionally, give the connector a custom name.</li>
                                                <li>Click the <strong>Connect GitHub</strong> button.</li>
                                                <li>If the connection is successful, you will be redirected and can start indexing from the Connectors page.</li>
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
