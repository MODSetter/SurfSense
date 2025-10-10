"use client";

import { ArrowLeft, Bot, Brain, Settings } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { LLMRoleManager } from "@/components/settings/llm-role-manager";
import { ModelConfigManager } from "@/components/settings/model-config-manager";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function SettingsPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);

	return (
		<div className="min-h-screen bg-background">
			<div className="container max-w-7xl mx-auto p-6 lg:p-8">
				<div className="space-y-8">
					{/* Header Section */}
					<div className="space-y-4">
						<div className="flex items-center space-x-4">
							{/* Back Button */}
							<button
								onClick={() => router.push(`/dashboard/${searchSpaceId}`)}
								className="flex items-center justify-center h-10 w-10 rounded-lg bg-primary/10 hover:bg-primary/20 transition-colors"
								aria-label="Back to Dashboard"
								type="button"
							>
								<ArrowLeft className="h-5 w-5 text-primary" />
							</button>
							<div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
								<Settings className="h-6 w-6 text-primary" />
							</div>
							<div className="space-y-1">
								<h1 className="text-3xl font-bold tracking-tight">Settings</h1>
								<p className="text-lg text-muted-foreground">
									Manage your LLM configurations and role assignments for this search space.
								</p>
							</div>
						</div>
						<Separator className="my-6" />
					</div>

					{/* Settings Content */}
					<Tabs defaultValue="models" className="space-y-8">
						<div className="overflow-x-auto">
							<TabsList className="grid w-full min-w-fit grid-cols-2 lg:w-auto lg:inline-grid">
								<TabsTrigger value="models" className="flex items-center gap-2 text-sm">
									<Bot className="h-4 w-4" />
									<span className="hidden sm:inline">Model Configs</span>
									<span className="sm:hidden">Models</span>
								</TabsTrigger>
								<TabsTrigger value="roles" className="flex items-center gap-2 text-sm">
									<Brain className="h-4 w-4" />
									<span className="hidden sm:inline">LLM Roles</span>
									<span className="sm:hidden">Roles</span>
								</TabsTrigger>
							</TabsList>
						</div>

						<TabsContent value="models" className="space-y-6">
							<ModelConfigManager searchSpaceId={searchSpaceId} />
						</TabsContent>

						<TabsContent value="roles" className="space-y-6">
							<LLMRoleManager searchSpaceId={searchSpaceId} />
						</TabsContent>
					</Tabs>
				</div>
			</div>
		</div>
	);
}
