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
} from "@tabler/icons-react";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

// Define connector categories and their connectors
const connectorCategories = [
  {
    id: "search-engines",
    title: "Search Engines",
    description: "Connect to search engines to enhance your research capabilities.",
    icon: <IconSearch className="h-5 w-5" />,
    connectors: [
      {
        id: "tavily-api",
        title: "Tavily Search API",
        description: "Connect to Tavily Search API to search the web.",
        icon: <IconSearch className="h-6 w-6" />,
        status: "available",
      },
      {
        id: "serper-api",
        title: "Serper API",
        description: "Connect to Serper API to search the web.",
        icon: <IconBrandGoogle className="h-6 w-6" />,
        status: "coming-soon",
      },
    ],
  },
  {
    id: "team-chats",
    title: "Team Chats",
    description: "Connect to your team communication platforms.",
    icon: <IconMessages className="h-5 w-5" />,
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
    description: "Connect to your knowledge bases and documentation.",
    icon: <IconDatabase className="h-5 w-5" />,
    connectors: [
      {
        id: "notion-connector",
        title: "Notion",
        description: "Connect to your Notion workspace to access pages and databases.",
        icon: <IconBrandNotion className="h-6 w-6" />,
        status: "available",
      },
      {
        id: "github",
        title: "GitHub",
        description: "Connect to GitHub repositories to access code and documentation.",
        icon: <IconBrandGithub className="h-6 w-6" />,
        status: "coming-soon",
      },
    ],
  },
  {
    id: "communication",
    title: "Communication",
    description: "Connect to your email and meeting platforms.",
    icon: <IconMail className="h-5 w-5" />,
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
  const [expandedCategories, setExpandedCategories] = useState<string[]>(["search-engines"]);

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
        {connectorCategories.map((category, categoryIndex) => (
          <Collapsible
            key={category.id}
            open={expandedCategories.includes(category.id)}
            onOpenChange={() => toggleCategory(category.id)}
            className="border rounded-lg overflow-hidden bg-card"
          >
            <CollapsibleTrigger asChild>
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: categoryIndex * 0.1 }}
                className="p-4 flex items-center justify-between cursor-pointer hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-md bg-primary/10 text-primary">
                    {category.icon}
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold">{category.title}</h2>
                    <p className="text-sm text-muted-foreground">{category.description}</p>
                  </div>
                </div>
                <IconChevronRight 
                  className={cn(
                    "h-5 w-5 text-muted-foreground transition-transform duration-200",
                    expandedCategories.includes(category.id) && "rotate-90"
                  )} 
                />
              </motion.div>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <Separator />
              <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <AnimatePresence>
                  {category.connectors.map((connector, index) => (
                    <motion.div
                      key={connector.id}
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ 
                        duration: 0.2, 
                        delay: index * 0.05,
                        type: "spring",
                        stiffness: 300,
                        damping: 30
                      }}
                      className={cn(
                        "relative group flex flex-col p-4 rounded-lg border",
                        connector.status === "coming-soon" ? "opacity-70" : ""
                      )}
                    >
                      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition duration-200 bg-gradient-to-t from-accent/50 to-transparent rounded-lg pointer-events-none" />
                      
                      <div className="mb-4 relative z-10 text-primary">
                        {connector.icon}
                      </div>
                      
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-lg font-semibold group-hover:translate-x-1 transition duration-200">
                          {connector.title}
                        </h3>
                        {connector.status === "coming-soon" && (
                          <span className="text-xs bg-muted px-2 py-1 rounded-full">Coming soon</span>
                        )}
                      </div>
                      
                      <p className="text-sm text-muted-foreground mb-4 flex-grow">
                        {connector.description}
                      </p>
                      
                      {connector.status === "available" ? (
                        <Link 
                          href={`/dashboard/${searchSpaceId}/connectors/add/${connector.id}`}
                          className="w-full mt-auto"
                        >
                          <Button 
                            variant="default"
                            className="w-full"
                          >
                            Connect
                          </Button>
                        </Link>
                      ) : (
                        <Button 
                          variant="outline"
                          className="w-full mt-auto"
                          disabled
                        >
                          Notify Me
                        </Button>
                      )}
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            </CollapsibleContent>
          </Collapsible>
        ))}
      </div>
    </div>
  );
}
