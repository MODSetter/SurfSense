"use client";
import { cn } from "@/lib/utils";
import {
  IconBrandGoogle,
  IconBrandSlack,
  IconBrandWindows,
  IconBrandDiscord,
  IconSearch,
  IconMessages,
  IconDatabase,
  IconCloud,
  IconBrandGithub,
  IconBrandNotion,
  IconMail,
  IconBrandZoom,
  IconChevronRight,
  IconWorldWww,
} from "@tabler/icons-react";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useForm } from "react-hook-form";

// Define the Connector type
interface Connector {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  status: "available" | "coming-soon" | "connected"; // Added connected status example
}

interface ConnectorCategory {
  id: string;
  title: string;
  connectors: Connector[];
}

// Define connector categories and their connectors
const connectorCategories: ConnectorCategory[] = [
  {
    id: "search-engines",
    title: "Search Engines",
    connectors: [
      {
        id: "web-search",
        title: "Web Search",
        description: "Enable web search capabilities for broader context.",
        icon: <IconWorldWww className="h-6 w-6" />,
        status: "available", // Example status
        // Potentially add config form here if needed (e.g., choosing provider)
      },
      // Add other search engine connectors like Tavily, Serper if they have UI config
    ],
  },
  {
    id: "team-chats",
    title: "Team Chats",
    connectors: [
      {
        id: "slack-connector",
        title: "Slack",
        description: "Connect to your Slack workspace to access messages and channels.",
        icon: <IconBrandSlack className="h-6 w-6" />,
        status: "available",
      },
      {
        id: "ms-teams",
        title: "Microsoft Teams",
        description: "Connect to Microsoft Teams to access your team's conversations.",
        icon: <IconBrandWindows className="h-6 w-6" />,
        status: "coming-soon",
      },
      {
        id: "discord",
        title: "Discord",
        description: "Connect to Discord servers to access messages and channels.",
        icon: <IconBrandDiscord className="h-6 w-6" />,
        status: "coming-soon",
      },
    ],
  },
  {
    id: "knowledge-bases",
    title: "Knowledge Bases",
    connectors: [
      {
        id: "notion-connector",
        title: "Notion",
        description: "Connect to your Notion workspace to access pages and databases.",
        icon: <IconBrandNotion className="h-6 w-6" />,
        status: "available",
        // No form here, assumes it links to its own page
      },
      {
        id: "github-connector", // Keep the id simple
        title: "GitHub",
        description: "Connect a GitHub PAT to index code and docs from accessible repositories.",
        icon: <IconBrandGithub className="h-6 w-6" />,
        status: "available",
      },
    ],
  },
  {
    id: "communication",
    title: "Communication",
    connectors: [
      {
        id: "gmail",
        title: "Gmail",
        description: "Connect to your Gmail account to access emails.",
        icon: <IconMail className="h-6 w-6" />,
        status: "coming-soon",
      },
      {
        id: "zoom",
        title: "Zoom",
        description: "Connect to Zoom to access meeting recordings and transcripts.",
        icon: <IconBrandZoom className="h-6 w-6" />,
        status: "coming-soon",
      },
    ],
  },
];

export default function ConnectorsPage() {
  const params = useParams();
  const searchSpaceId = params.search_space_id as string;
  const [expandedCategories, setExpandedCategories] = useState<string[]>(["search-engines", "knowledge-bases"]);

  const toggleCategory = (categoryId: string) => {
    setExpandedCategories(prev => 
      prev.includes(categoryId) 
        ? prev.filter(id => id !== categoryId) 
        : [...prev, categoryId]
    );
  };

  return (
    <div className="container mx-auto py-8 max-w-6xl">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8 text-center"
      >
        <h1 className="text-3xl font-bold tracking-tight">Connect Your Tools</h1>
        <p className="text-muted-foreground mt-2">
          Integrate with your favorite services to enhance your research capabilities.
        </p>
      </motion.div>

      <div className="space-y-6">
        {connectorCategories.map((category) => (
          <Collapsible
            key={category.id}
            open={expandedCategories.includes(category.id)}
            onOpenChange={() => toggleCategory(category.id)}
            className="space-y-2"
          >
            <div className="flex items-center justify-between space-x-4 px-1">
              <h3 className="text-lg font-semibold dark:text-gray-200">{category.title}</h3>
              <CollapsibleTrigger asChild>
                {/* Replace with your preferred expand/collapse icon/button */}
                <button className="text-sm text-indigo-600 hover:underline dark:text-indigo-400">
                  {expandedCategories.includes(category.id) ? "Collapse" : "Expand"}
                </button>
              </CollapsibleTrigger>
            </div>
            <CollapsibleContent>
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 p-1">
                {category.connectors.map((connector) => (
                  <div key={connector.id} className="col-span-1 flex flex-col divide-y divide-gray-200 dark:divide-gray-700 rounded-lg bg-white dark:bg-gray-800 shadow">
                    <div className="flex w-full items-center justify-between space-x-6 p-6 flex-grow">
                      <div className="flex-1 truncate">
                        <div className="flex items-center space-x-3">
                          <span className="text-gray-900 dark:text-gray-100">{connector.icon}</span>
                          <h3 className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
                            {connector.title}
                          </h3>
                          {connector.status === "coming-soon" && (
                            <span className="inline-block flex-shrink-0 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                              Coming soon
                            </span>
                          )}
                          {/* TODO: Add 'Connected' badge based on actual state */} 
                        </div>
                        <p className="mt-1 truncate text-sm text-gray-500 dark:text-gray-400">
                          {connector.description}
                        </p>
                      </div>
                    </div>
                    {/* Always render Link button if available */}
                    {connector.status === 'available' && (
                      <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700">
                        <Link href={`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`}>
                          <Button variant="default" className="w-full">
                            Connect
                          </Button>
                        </Link>
                      </div>
                    )}
                    {connector.status === 'coming-soon' && (
                      <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700">
                        <Button variant="outline" disabled className="w-full">
                          Coming Soon
                        </Button>
                      </div>
                    )}
                    {/* TODO: Add logic for 'connected' status */}
                  </div>
                ))}
              </div>
            </CollapsibleContent>
            <Separator className="my-4" />
          </Collapsible>
        ))}
      </div>
    </div>
  );
}
