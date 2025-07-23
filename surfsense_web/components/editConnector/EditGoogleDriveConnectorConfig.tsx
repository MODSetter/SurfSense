import React from 'react';
import { UseFormReturn } from 'react-hook-form';
import { FormField, FormItem, FormLabel, FormControl, FormDescription, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Edit, Cloud, Loader2, CircleAlert } from 'lucide-react';

// Types needed from parent
interface GoogleDriveFile {
    id: string;
    name: string;
    mimeType: string;
    size?: string;
    modifiedTime: string;
    webViewLink: string;
    parents?: string[];
}

type GoogleDriveTokensFormValues = { 
    access_token: string; 
    refresh_token: string; 
};

type EditMode = 'viewing' | 'editing_files';

interface EditGoogleDriveConnectorConfigProps {
    // State from parent
    editMode: EditMode;
    originalTokens: { access_token: string; refresh_token: string };
    currentSelectedFiles: string[];
    fetchedFiles: GoogleDriveFile[] | null;
    newSelectedFiles: string[];
    isFetchingFiles: boolean;
    // Forms from parent
    tokensForm: UseFormReturn<GoogleDriveTokensFormValues>;
    // Handlers from parent
    setEditMode: (mode: EditMode) => void;
    handleFetchFiles: (values: GoogleDriveTokensFormValues) => Promise<void>;
    handleFileSelectionChange: (fileId: string, checked: boolean) => void;
    setNewSelectedFiles: React.Dispatch<React.SetStateAction<string[]>>;
    setFetchedFiles: React.Dispatch<React.SetStateAction<GoogleDriveFile[] | null>>;
}

export function EditGoogleDriveConnectorConfig({
    editMode,
    originalTokens,
    currentSelectedFiles,
    fetchedFiles,
    newSelectedFiles,
    isFetchingFiles,
    tokensForm,
    setEditMode,
    handleFetchFiles,
    handleFileSelectionChange,
    setNewSelectedFiles,
    setFetchedFiles,
}: EditGoogleDriveConnectorConfigProps) {
    
    // Format file size
    const formatFileSize = (size?: string): string => {
        if (!size) return "Unknown size";
        const bytes = parseInt(size);
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const handleCancelEdit = () => {
        setEditMode('viewing');
        setFetchedFiles(null);
        setNewSelectedFiles(currentSelectedFiles);
        tokensForm.reset({
            access_token: originalTokens.access_token,
            refresh_token: originalTokens.refresh_token,
        });
    };

    if (editMode === 'viewing') {
        return (
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-medium">Google Drive Configuration</h3>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setEditMode('editing_files')}
                        className="flex items-center gap-2"
                    >
                        <Edit className="h-4 w-4" />
                        Edit Files
                    </Button>
                </div>
                
                <div className="grid grid-cols-1 gap-4">
                    <div>
                        <label className="text-sm font-medium text-muted-foreground">Selected Files</label>
                        <div className="mt-2 p-3 rounded-md border bg-muted/50">
                            <span className="text-sm">{currentSelectedFiles.length} files selected</span>
                        </div>
                    </div>
                    
                    <div>
                        <label className="text-sm font-medium text-muted-foreground">OAuth Status</label>
                        <div className="mt-2 p-3 rounded-md border bg-muted/50">
                            <span className="text-sm text-green-600">✓ Authenticated</span>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium">Edit Google Drive Files</h3>
                <div className="flex gap-2">
                    <Button variant="outline" onClick={handleCancelEdit}>
                        Cancel
                    </Button>
                </div>
            </div>

            <Alert>
                <Cloud className="h-4 w-4" />
                <AlertTitle>Re-authenticate with Google Drive</AlertTitle>
                <AlertDescription>
                    To change your file selection, you'll need to re-authenticate with Google Drive to fetch your current files.
                </AlertDescription>
            </Alert>

            <form onSubmit={tokensForm.handleSubmit(handleFetchFiles)} className="space-y-4">
                <FormField
                    control={tokensForm.control}
                    name="access_token"
                    render={({ field }) => (
                        <FormItem>
                            <FormLabel>Access Token</FormLabel>
                            <FormControl>
                                <Input
                                    type="password"
                                    placeholder="OAuth2 Access Token"
                                    {...field}
                                />
                            </FormControl>
                            <FormDescription>
                                Google OAuth2 access token (will be refreshed automatically)
                            </FormDescription>
                            <FormMessage />
                        </FormItem>
                    )}
                />

                <FormField
                    control={tokensForm.control}
                    name="refresh_token"
                    render={({ field }) => (
                        <FormItem>
                            <FormLabel>Refresh Token</FormLabel>
                            <FormControl>
                                <Input
                                    type="password"
                                    placeholder="OAuth2 Refresh Token"
                                    {...field}
                                />
                            </FormControl>
                            <FormDescription>
                                Google OAuth2 refresh token for long-term access
                            </FormDescription>
                            <FormMessage />
                        </FormItem>
                    )}
                />

                <Button type="submit" disabled={isFetchingFiles}>
                    {isFetchingFiles ? (
                        <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Fetching Files...
                        </>
                    ) : (
                        'Fetch Files'
                    )}
                </Button>
            </form>

            {/* Files Selection */}
            {fetchedFiles && (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h4 className="font-medium">Select Files ({newSelectedFiles.length} selected)</h4>
                    </div>
                    
                    {fetchedFiles.length === 0 ? (
                        <Alert variant="destructive">
                            <CircleAlert className="h-4 w-4" />
                            <AlertTitle>No Files Found</AlertTitle>
                            <AlertDescription>
                                No files were found in your Google Drive. Please make sure you have files and try again.
                            </AlertDescription>
                        </Alert>
                    ) : (
                        <div className="h-64 w-full rounded-md border p-4 overflow-y-auto">
                            {fetchedFiles.map((file) => (
                                <div key={file.id} className="flex items-center space-x-2 mb-2 py-1">
                                    <Checkbox
                                        id={`file-${file.id}`}
                                        checked={newSelectedFiles.includes(file.id)}
                                        onCheckedChange={(checked) => handleFileSelectionChange(file.id, !!checked)}
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
                    )}
                </div>
            )}

            {/* Loading skeleton for files */}
            {isFetchingFiles && !fetchedFiles && (
                <div className="space-y-2">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-64 w-full" />
                </div>
            )}
        </div>
    );
}