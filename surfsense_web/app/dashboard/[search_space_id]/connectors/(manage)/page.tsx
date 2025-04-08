"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Edit, Plus, Search, Trash2, ExternalLink, RefreshCw } from "lucide-react";

import { useSearchSourceConnectors } from "@/hooks/useSearchSourceConnectors";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

// Helper function to get connector type display name
const getConnectorTypeDisplay = (type: string): string => {
  const typeMap: Record<string, string> = {
    "SERPER_API": "Serper API",
    "TAVILY_API": "Tavily API",
    "SLACK_CONNECTOR": "Slack",
    "NOTION_CONNECTOR": "Notion",
    // Add other connector types here as needed
  };
  return typeMap[type] || type;
};

// Helper function to format date with time
const formatDateTime = (dateString: string | null): string => {
  if (!dateString) return "Never";
  
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
};

export default function ConnectorsPage() {
  const router = useRouter();
  const params = useParams();
  const searchSpaceId = params.search_space_id as string;
  
  const { connectors, isLoading, error, deleteConnector, indexConnector } = useSearchSourceConnectors();
  const [connectorToDelete, setConnectorToDelete] = useState<number | null>(null);
  const [indexingConnectorId, setIndexingConnectorId] = useState<number | null>(null);

  useEffect(() => {
    if (error) {
      toast.error("Failed to load connectors");
      console.error("Error fetching connectors:", error);
    }
  }, [error]);

  // Handle connector deletion
  const handleDeleteConnector = async () => {
    if (connectorToDelete === null) return;
    
    try {
      await deleteConnector(connectorToDelete);
      toast.success("Connector deleted successfully");
    } catch (error) {
      console.error("Error deleting connector:", error);
      toast.error("Failed to delete connector");
    } finally {
      setConnectorToDelete(null);
    }
  };

  // Handle connector indexing
  const handleIndexConnector = async (connectorId: number) => {
    setIndexingConnectorId(connectorId);
    try {
      await indexConnector(connectorId, searchSpaceId);
      toast.success("Connector content indexed successfully");
    } catch (error) {
      console.error("Error indexing connector content:", error);
      toast.error(error instanceof Error ? error.message : "Failed to index connector content");
    } finally {
      setIndexingConnectorId(null);
    }
  };

  return (
    <div className="container mx-auto py-8 max-w-6xl">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8 flex items-center justify-between"
      >
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Connectors</h1>
          <p className="text-muted-foreground mt-2">
            Manage your connected services and data sources.
          </p>
        </div>
        <Button onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/add`)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Connector
        </Button>
      </motion.div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Your Connectors</CardTitle>
          <CardDescription>
            View and manage all your connected services.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <div className="animate-pulse text-center">
                <div className="h-6 w-32 bg-muted rounded mx-auto mb-2"></div>
                <div className="h-4 w-48 bg-muted rounded mx-auto"></div>
              </div>
            </div>
          ) : connectors.length === 0 ? (
            <div className="text-center py-12">
              <h3 className="text-lg font-medium mb-2">No connectors found</h3>
              <p className="text-muted-foreground mb-6">
                You haven't added any connectors yet. Add one to enhance your search capabilities.
              </p>
              <Button onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/add`)}>
                <Plus className="mr-2 h-4 w-4" />
                Add Your First Connector
              </Button>
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Last Indexed</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {connectors.map((connector) => (
                    <TableRow key={connector.id}>
                      <TableCell className="font-medium">{connector.name}</TableCell>
                      <TableCell>{getConnectorTypeDisplay(connector.connector_type)}</TableCell>
                      <TableCell>
                        {connector.is_indexable 
                          ? formatDateTime(connector.last_indexed_at)
                          : "Not indexable"}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          {connector.is_indexable && (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleIndexConnector(connector.id)}
                                    disabled={indexingConnectorId === connector.id}
                                  >
                                    {indexingConnectorId === connector.id ? (
                                      <RefreshCw className="h-4 w-4 animate-spin" />
                                    ) : (
                                      <RefreshCw className="h-4 w-4" />
                                    )}
                                    <span className="sr-only">Index Content</span>
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>
                                  <p>Index Content</p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors/${connector.id}`)}
                          >
                            <Edit className="h-4 w-4" />
                            <span className="sr-only">Edit</span>
                          </Button>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-destructive-foreground hover:bg-destructive/10"
                                onClick={() => setConnectorToDelete(connector.id)}
                              >
                                <Trash2 className="h-4 w-4" />
                                <span className="sr-only">Delete</span>
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Delete Connector</AlertDialogTitle>
                                <AlertDialogDescription>
                                  Are you sure you want to delete this connector? This action cannot be undone.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel onClick={() => setConnectorToDelete(null)}>
                                  Cancel
                                </AlertDialogCancel>
                                <AlertDialogAction
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                  onClick={handleDeleteConnector}
                                >
                                  Delete
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
} 