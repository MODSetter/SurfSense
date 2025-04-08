"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { motion } from "framer-motion";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { toast } from "sonner";
import { ArrowLeft, Check, Info, Loader2 } from "lucide-react";

import { useSearchSourceConnectors, SearchSourceConnector } from "@/hooks/useSearchSourceConnectors";
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
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";

// Define the form schema with Zod
const apiConnectorFormSchema = z.object({
  name: z.string().min(3, {
    message: "Connector name must be at least 3 characters.",
  }),
  api_key: z.string().min(10, {
    message: "API key is required and must be valid.",
  }),
});

// Helper function to get connector type display name
const getConnectorTypeDisplay = (type: string): string => {
  const typeMap: Record<string, string> = {
    "SERPER_API": "Serper API",
    "TAVILY_API": "Tavily API",
    "SLACK_CONNECTOR": "Slack Connector",
    "NOTION_CONNECTOR": "Notion Connector",
    // Add other connector types here as needed
  };
  return typeMap[type] || type;
};

// Define the type for the form values
type ApiConnectorFormValues = z.infer<typeof apiConnectorFormSchema>;

export default function EditConnectorPage() {
  const router = useRouter();
  const params = useParams();
  const searchSpaceId = params.search_space_id as string;
  const connectorId = parseInt(params.connector_id as string, 10);
  
  const { connectors, updateConnector } = useSearchSourceConnectors();
  const [connector, setConnector] = useState<SearchSourceConnector | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Initialize the form
  const form = useForm<ApiConnectorFormValues>({
    resolver: zodResolver(apiConnectorFormSchema),
    defaultValues: {
      name: "",
      api_key: "",
    },
  });

  // Get API key field name based on connector type
  const getApiKeyFieldName = (connectorType: string): string => {
    const fieldMap: Record<string, string> = {
      "SERPER_API": "SERPER_API_KEY",
      "TAVILY_API": "TAVILY_API_KEY",
      "SLACK_CONNECTOR": "SLACK_BOT_TOKEN",
      "NOTION_CONNECTOR": "NOTION_INTEGRATION_TOKEN"
    };
    return fieldMap[connectorType] || "";
  };

  // Find connector in the list
  useEffect(() => {
    const currentConnector = connectors.find(c => c.id === connectorId);
    
    if (currentConnector) {
      setConnector(currentConnector);
      
      // Check if connector type is supported
      const apiKeyField = getApiKeyFieldName(currentConnector.connector_type);
      if (apiKeyField) {
        form.reset({
          name: currentConnector.name,
          api_key: currentConnector.config[apiKeyField] || "",
        });
      } else {
        // Redirect if not a supported connector type
        toast.error("This connector type is not supported for editing");
        router.push(`/dashboard/${searchSpaceId}/connectors`);
      }
      
      setIsLoading(false);
    } else if (!isLoading && connectors.length > 0) {
      // If connectors are loaded but this one isn't found
      toast.error("Connector not found");
      router.push(`/dashboard/${searchSpaceId}/connectors`);
    }
  }, [connectors, connectorId, form, router, searchSpaceId, isLoading]);

  // Handle form submission
  const onSubmit = async (values: ApiConnectorFormValues) => {
    if (!connector) return;
    
    setIsSubmitting(true);
    try {
      const apiKeyField = getApiKeyFieldName(connector.connector_type);
      
      // Only update the API key if a new one was provided
      const updatedConfig = { ...connector.config };
      if (values.api_key) {
        updatedConfig[apiKeyField] = values.api_key;
      }

      await updateConnector(connectorId, {
        name: values.name,
        connector_type: connector.connector_type,
        config: updatedConfig,
      });

      toast.success("Connector updated successfully!");
      router.push(`/dashboard/${searchSpaceId}/connectors`);
    } catch (error) {
      console.error("Error updating connector:", error);
      toast.error(error instanceof Error ? error.message : "Failed to update connector");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto py-8 max-w-3xl flex justify-center items-center min-h-[60vh]">
        <div className="animate-pulse text-center">
          <div className="h-8 w-48 bg-muted rounded mx-auto mb-4"></div>
          <div className="h-4 w-64 bg-muted rounded mx-auto"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-3xl">
      <Button
        variant="ghost"
        className="mb-6"
        onClick={() => router.push(`/dashboard/${searchSpaceId}/connectors`)}
      >
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Connectors
      </Button>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <Card className="border-2 border-border">
          <CardHeader>
            <CardTitle className="text-2xl font-bold">
              Edit {connector ? getConnectorTypeDisplay(connector.connector_type) : ""} Connector
            </CardTitle>
            <CardDescription>
              Update your connector settings.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Alert className="mb-6 bg-muted">
              <Info className="h-4 w-4" />
              <AlertTitle>API Key Security</AlertTitle>
              <AlertDescription>
                Your API key is stored securely. For security reasons, we don't display your existing API key.
                If you don't update the API key field, your existing key will be preserved.
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
                        <Input placeholder="My API Connector" {...field} />
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
                  name="api_key"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        {connector?.connector_type === "SLACK_CONNECTOR" 
                          ? "Slack Bot Token" 
                          : connector?.connector_type === "NOTION_CONNECTOR" 
                            ? "Notion Integration Token" 
                            : "API Key"}
                      </FormLabel>
                      <FormControl>
                        <Input 
                          type="password" 
                          placeholder={
                            connector?.connector_type === "SLACK_CONNECTOR" 
                              ? "Enter your Slack Bot Token" 
                              : connector?.connector_type === "NOTION_CONNECTOR" 
                                ? "Enter your Notion Integration Token" 
                                : "Enter your API key"
                          } 
                          {...field} 
                        />
                      </FormControl>
                      <FormDescription>
                        {connector?.connector_type === "SLACK_CONNECTOR" 
                          ? "Enter a new Slack Bot Token or leave blank to keep your existing token." 
                          : connector?.connector_type === "NOTION_CONNECTOR" 
                            ? "Enter a new Notion Integration Token or leave blank to keep your existing token." 
                            : "Enter a new API key or leave blank to keep your existing key."}
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
                        Updating...
                      </>
                    ) : (
                      <>
                        <Check className="mr-2 h-4 w-4" />
                        Update Connector
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </Form>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
} 