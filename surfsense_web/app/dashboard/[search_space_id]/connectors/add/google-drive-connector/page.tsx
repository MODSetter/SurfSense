"use client";

import { useState, useEffect } from "react";
// @ts-ignore - Next.js navigation types
import { useRouter, useParams } from "next/navigation";
import { motion } from "framer-motion";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { toast } from "sonner";
// @ts-ignore - Lucide React types
import { ArrowLeft, Check, Info, Loader2, Cloud, CircleAlert, FileText } from "lucide-react";

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
import { Checkbox } from "@/components/ui/checkbox";

// Define the form schema for OAuth setup step
const googleDriveFormSchema = z.object({
    name: z.string().min(3, {
        message: "Connector name must be at least 3 characters.",
    })
});

// Define the type for the form values
type GoogleDriveFormValues = z.infer<typeof googleDriveFormSchema>;

// Type for Google Drive files
interface GoogleDriveFile {
    id: string;
    name: string;
    mimeType: string;
    size?: string;
    modifiedTime: string;
    webViewLink: string;
    parents?: string[];
}

export default function GoogleDriveConnectorPage() {
    const router = useRouter();
    const params = useParams();
    const searchSpaceId = params.search_space_id as string;
    const [step, setStep] = useState<'setup_oauth' | 'select_files'>('setup_oauth');
    const [isAuthenticating, setIsAuthenticating] = useState(false);
    const [isCreatingConnector, setIsCreatingConnector] = useState(false);
    const [files, setFiles] = useState<GoogleDriveFile[]>([]);
    const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
    const [connectorName, setConnectorName] = useState<string>("Google Drive Connector");
    const [oauthTokens, setOauthTokens] = useState<{access_token: string, refresh_token: string} | null>(null);

    const { createConnector } = useSearchSourceConnectors();

    // Initialize the form for connector setup
    const form = useForm<GoogleDriveFormValues>({
        resolver: zodResolver(googleDriveFormSchema),
        defaultValues: {
            name: connectorName,
        },
    });

    // Handle OAuth success callback
    useEffect(() => {
        if (typeof window === 'undefined') return;

        const urlParams = new URLSearchParams(window.location.search);
        const oauthSuccess = urlParams.get('oauth_success');
        const oauthData = urlParams.get('data');

        if (oauthSuccess === 'true' && oauthData) {
            try {
                const data = JSON.parse(decodeURIComponent(oauthData));
                const { access_token, refresh_token, files: driveFiles, connector_name } = data;

                if (access_token && driveFiles) {
                    setOauthTokens({ access_token, refresh_token });
                    setFiles(driveFiles);
                    setConnectorName(connector_name || connectorName);
                    setStep('select_files');
                    setIsAuthenticating(false);

                    // Clean up URL parameters
                    const cleanUrl = window.location.pathname;
                    window.history.replaceState({}, document.title, cleanUrl);

                    toast.success("Successfully connected to Google Drive!");
                }
            } catch (error) {
                console.error('Error parsing OAuth data:', error);
                toast.error("Failed to process Google Drive authentication data.");
                setIsAuthenticating(false);
            }
        }

        // Handle OAuth errors
        const error = urlParams.get('error');
        if (error) {
            toast.error(decodeURIComponent(error));
            setIsAuthenticating(false);
            
            // Clean up URL parameters
            const cleanUrl = window.location.pathname;
            window.history.replaceState({}, document.title, cleanUrl);
        }
    }, [connectorName]);

    // Function to initiate OAuth flow
    const initiateOAuthFlow = async (values: GoogleDriveFormValues) => {
        setIsAuthenticating(true);
        setConnectorName(values.name);
        
        try {
            // OAuth2 configuration
            const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
            const redirectUri = `${window.location.origin}/auth/google/callback`;
            const scope = 'https://www.googleapis.com/auth/drive.readonly';
            
            if (!clientId) {
                throw new Error('Google Client ID not configured. Please set NEXT_PUBLIC_GOOGLE_CLIENT_ID environment variable.');
            }
            
            // Create OAuth2 authorization URL
            const authUrl = new URL('https://accounts.google.com/o/oauth2/v2/auth');
            authUrl.searchParams.append('client_id', clientId);
            authUrl.searchParams.append('redirect_uri', redirectUri);
            authUrl.searchParams.append('response_type', 'code');
            authUrl.searchParams.append('scope', scope);
            authUrl.searchParams.append('access_type', 'offline');
            authUrl.searchParams.append('prompt', 'consent');
            authUrl.searchParams.append('state', JSON.stringify({ 
                connector_name: values.name,
                search_space_id: searchSpaceId 
            }));
            
            toast.info("Redirecting to Google for authorization...");
            
            // Store the connector name for when we return
            localStorage.setItem('google_drive_connector_name', values.name);
            
            // Redirect to Google OAuth
            window.location.href = authUrl.toString();
            
        } catch (error) {
            console.error("Error during OAuth flow:", error);
            const errorMessage = error instanceof Error ? error.message : "Failed to initiate Google authentication.";
            toast.error(errorMessage);
            setIsAuthenticating(false);
        }
    };

    // Handle final connector creation
    const handleCreateConnector = async () => {
        if (selectedFiles.length === 0) {
            toast.warning("Please select at least one file to index.");
            return;
        }

        if (!oauthTokens) {
            toast.error("OAuth tokens not found. Please restart the setup process.");
            return;
        }

        setIsCreatingConnector(true);
        try {
            // Get selected file objects
            const selectedFileObjects = files.filter(file => selectedFiles.includes(file.id));

            await createConnector({
                name: connectorName,
                connector_type: "GOOGLE_DRIVE_CONNECTOR",
                config: {
                    GOOGLE_OAUTH_TOKEN: oauthTokens.access_token,
                    GOOGLE_REFRESH_TOKEN: oauthTokens.refresh_token,
                    selected_files: selectedFileObjects,
                },
                is_indexable: true,
                last_indexed_at: null,
            });

            toast.success("Google Drive connector created successfully!");
            router.push(`/dashboard/${searchSpaceId}/connectors`);
        } catch (error) {
            console.error("Error creating Google Drive connector:", error);
            const errorMessage = error instanceof Error ? error.message : "Failed to create Google Drive connector.";
            toast.error(errorMessage);
        } finally {
            setIsCreatingConnector(false);
        }
    };

    // Handle checkbox changes
    const handleFileSelection = (fileId: string, checked: boolean) => {
        setSelectedFiles(prev =>
            checked
                ? [...prev, fileId]
                : prev.filter(id => id !== fileId)
        );
    };

    // Format file size
    const formatFileSize = (size?: string): string => {
        if (!size) return "Unknown size";
        const bytes = parseInt(size);
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <div className="container mx-auto py-8 max-w-3xl">
            <Button
                variant="ghost"
                className="mb-6"
                onClick={() => {
                    if (step === 'select_files') {
                        setStep('setup_oauth');
                        setFiles([]);
                        setSelectedFiles([]);
                        setOauthTokens(null);
                        form.reset({ name: connectorName });
                    } else {
                        router.push(`/dashboard/${searchSpaceId}/connectors/add`);
                    }
                }}
            >
                <ArrowLeft className="mr-2 h-4 w-4" />
                {step === 'select_files' ? "Back to Setup" : "Back to Add Connectors"}
            </Button>

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
            >
                <Tabs defaultValue="connect" className="w-full">
                    <TabsList className="grid w-full grid-cols-2 mb-6">
                        <TabsTrigger value="connect">Connect Google Drive</TabsTrigger>
                        <TabsTrigger value="documentation">Setup Guide</TabsTrigger>
                    </TabsList>

                    <TabsContent value="connect">
                        <Card className="border-2 border-border">
                            <CardHeader>
                                <CardTitle className="text-2xl font-bold flex items-center gap-2">
                                    {step === 'setup_oauth' ? <Cloud className="h-6 w-6" /> : <FileText className="h-6 w-6" />}
                                    {step === 'setup_oauth' ? "Connect Google Drive Account" : "Select Files to Index"}
                                </CardTitle>
                                <CardDescription>
                                    {step === 'setup_oauth'
                                        ? "Authenticate with Google Drive to access your files and documents."
                                        : `Select which files you want SurfSense to index for search. Found ${files.length} files accessible via your Google Drive.`
                                    }
                                </CardDescription>
                            </CardHeader>

                            <Form {...form}>
                                {step === 'setup_oauth' && (
                                    <CardContent>
                                        <Alert className="mb-6 bg-muted">
                                            <Info className="h-4 w-4" />
                                            <AlertTitle>Google OAuth Required</AlertTitle>
                                            <AlertDescription>
                                                You'll be redirected to Google to authorize SurfSense to access your Google Drive files. 
                                                We only request read-only access to ensure your data remains secure.
                                            </AlertDescription>
                                        </Alert>

                                        <form onSubmit={form.handleSubmit(initiateOAuthFlow)} className="space-y-6">
                                            <FormField
                                                control={form.control}
                                                name="name"
                                                render={({ field }) => (
                                                    <FormItem>
                                                        <FormLabel>Connector Name</FormLabel>
                                                        <FormControl>
                                                            <Input placeholder="My Google Drive Connector" {...field} />
                                                        </FormControl>
                                                        <FormDescription>
                                                            A friendly name to identify this Google Drive connection.
                                                        </FormDescription>
                                                        <FormMessage />
                                                    </FormItem>
                                                )}
                                            />

                                            <div className="flex justify-end">
                                                <Button
                                                    type="submit"
                                                    disabled={isAuthenticating}
                                                    className="w-full sm:w-auto"
                                                >
                                                    {isAuthenticating ? (
                                                        <>
                                                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                            Authenticating...
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Cloud className="mr-2 h-4 w-4" />
                                                            Connect to Google Drive
                                                        </>
                                                    )}
                                                </Button>
                                            </div>
                                        </form>
                                    </CardContent>
                                )}

                                {step === 'select_files' && (
                                    <CardContent>
                                        {files.length === 0 ? (
                                            <Alert variant="destructive">
                                                <CircleAlert className="h-4 w-4" />
                                                <AlertTitle>No Files Found</AlertTitle>
                                                <AlertDescription>
                                                    No files were found in your Google Drive. Please make sure you have files in your drive and try again.
                                                </AlertDescription>
                                            </Alert>
                                        ) : (
                                            <div className="space-y-4">
                                                <FormLabel>Files ({selectedFiles.length} selected)</FormLabel>
                                                <div className="h-64 w-full rounded-md border p-4 overflow-y-auto">
                                                    {files.map((file) => (
                                                        <div key={file.id} className="flex items-center space-x-2 mb-2 py-1">
                                                            <Checkbox
                                                                id={`file-${file.id}`}
                                                                checked={selectedFiles.includes(file.id)}
                                                                onCheckedChange={(checked) => handleFileSelection(file.id, !!checked)}
                                                            />
                                                            <label
                                                                htmlFor={`file-${file.id}`}
                                                                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 flex-1"
                                                            >
                                                                <div className="flex justify-between items-center">
                                                                    <span>{file.name}</span>
                                                                    <span className="text-xs text-muted-foreground">
                                                                        {formatFileSize(file.size)}
                                                                    </span>
                                                                </div>
                                                                <div className="text-xs text-muted-foreground mt-1">
                                                                    {file.mimeType.includes('google-apps') 
                                                                        ? file.mimeType.split('.').pop()?.replace('-', ' ') 
                                                                        : file.mimeType}
                                                                </div>
                                                            </label>
                                                        </div>
                                                    ))}
                                                </div>
                                                <FormDescription>
                                                    Select the files you wish to index. Only checked files will be processed.
                                                </FormDescription>

                                                <div className="flex justify-between items-center pt-4">
                                                    <Button
                                                        variant="outline"
                                                        onClick={() => {
                                                            setStep('setup_oauth');
                                                            setFiles([]);
                                                            setSelectedFiles([]);
                                                            setOauthTokens(null);
                                                            form.reset({ name: connectorName });
                                                        }}
                                                    >
                                                        Back
                                                    </Button>
                                                    <Button
                                                        onClick={handleCreateConnector}
                                                        disabled={isCreatingConnector || selectedFiles.length === 0}
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
                                <h4 className="text-sm font-medium">What you get with Google Drive integration:</h4>
                                <ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
                                    <li>Search through Google Docs, Sheets, and Slides content</li>
                                    <li>Access PDFs, text files, and other supported document formats</li>
                                    <li>Connect your document knowledge directly to your search space</li>
                                    <li>Index your selected files for enhanced search capabilities</li>
                                </ul>
                            </CardFooter>
                        </Card>
                    </TabsContent>

                    <TabsContent value="documentation">
                        <Card className="border-2 border-border">
                            <CardHeader>
                                <CardTitle className="text-2xl font-bold">Google Drive Connector Setup Guide</CardTitle>
                                <CardDescription>
                                    Learn how to connect your Google Drive account and select files for indexing.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div>
                                    <h3 className="text-xl font-semibold mb-2">How it works</h3>
                                    <p className="text-muted-foreground">
                                        The Google Drive connector uses Google's OAuth 2.0 to securely authenticate with your Google Drive account. 
                                        After authentication, it fetches a list of your files. You then select which files you want to index. 
                                        The connector processes Google Workspace files (Docs, Sheets, Slides) and other supported formats.
                                    </p>
                                    <ul className="mt-2 list-disc pl-5 text-muted-foreground">
                                        <li>Supports Google Docs, Sheets, Slides, Forms, PDFs, and text files</li>
                                        <li>Large files (over 10MB) are skipped during indexing</li>
                                        <li>Only selected files are indexed and searchable</li>
                                        <li>Uses read-only permissions for maximum security</li>
                                    </ul>
                                </div>

                                <Accordion type="single" collapsible className="w-full">
                                    <AccordionItem value="setup_oauth">
                                        <AccordionTrigger className="text-lg font-medium">Step 1: OAuth Authentication</AccordionTrigger>
                                        <AccordionContent>
                                            <div className="space-y-6">
                                                <div>
                                                    <h4 className="font-medium mb-2">Authentication Process:</h4>
                                                    <ol className="list-decimal pl-5 space-y-3">
                                                        <li>Click "Connect to Google Drive" to start the OAuth flow</li>
                                                        <li>You'll be redirected to Google's authorization page</li>
                                                        <li>Sign in to your Google account if prompted</li>
                                                        <li>Review and accept the requested permissions (read-only access)</li>
                                                        <li>You'll be redirected back to SurfSense with access granted</li>
                                                        <li>The system will automatically fetch your available files</li>
                                                    </ol>
                                                </div>
                                            </div>
                                        </AccordionContent>
                                    </AccordionItem>

                                    <AccordionItem value="select_files">
                                        <AccordionTrigger className="text-lg font-medium">Step 2: File Selection</AccordionTrigger>
                                        <AccordionContent className="space-y-4">
                                            <ol className="list-decimal pl-5 space-y-3">
                                                <li>After successful authentication, you'll see a list of your Google Drive files</li>
                                                <li>Review the file list and select the documents you want to index</li>
                                                <li>Use the checkboxes to select individual files</li>
                                                <li>Review your selection count at the top of the list</li>
                                                <li>Click "Create Connector" to finalize the setup</li>
                                                <li>The connector will be created and ready for indexing</li>
                                            </ol>
                                        </AccordionContent>
                                    </AccordionItem>

                                    <AccordionItem value="security">
                                        <AccordionTrigger className="text-lg font-medium">Security & Privacy</AccordionTrigger>
                                        <AccordionContent className="space-y-4">
                                            <ul className="list-disc pl-5 space-y-2">
                                                <li>SurfSense requests only read-only access to your Google Drive</li>
                                                <li>We cannot modify, delete, or share your files</li>
                                                <li>OAuth tokens are stored securely and encrypted</li>
                                                <li>You can revoke access at any time from your Google Account settings</li>
                                                <li>Only selected files are processed and indexed</li>
                                            </ul>
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