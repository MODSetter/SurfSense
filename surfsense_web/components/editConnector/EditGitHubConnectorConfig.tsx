import { CircleAlert, Edit, KeyRound, Loader2 } from "lucide-react";
import type React from "react";
import type { UseFormReturn } from "react-hook-form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	FormControl,
	FormDescription,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

// Types needed from parent
interface GithubRepo {
	id: number;
	name: string;
	full_name: string;
	private: boolean;
	url: string;
	description: string | null;
	last_updated: string | null;
}
type GithubPatFormValues = { github_pat: string };
type EditMode = "viewing" | "editing_repos";

interface EditGitHubConnectorConfigProps {
	// State from parent
	editMode: EditMode;
	originalPat: string;
	currentSelectedRepos: string[];
	fetchedRepos: GithubRepo[] | null;
	newSelectedRepos: string[];
	isFetchingRepos: boolean;
	// Forms from parent
	patForm: UseFormReturn<GithubPatFormValues>;
	// Handlers from parent
	setEditMode: (mode: EditMode) => void;
	handleFetchRepositories: (values: GithubPatFormValues) => Promise<void>;
	handleRepoSelectionChange: (repoFullName: string, checked: boolean) => void;
	setNewSelectedRepos: React.Dispatch<React.SetStateAction<string[]>>;
	setFetchedRepos: React.Dispatch<React.SetStateAction<GithubRepo[] | null>>;
}

export function EditGitHubConnectorConfig({
	editMode,
	originalPat,
	currentSelectedRepos,
	fetchedRepos,
	newSelectedRepos,
	isFetchingRepos,
	patForm,
	setEditMode,
	handleFetchRepositories,
	handleRepoSelectionChange,
	setNewSelectedRepos,
	setFetchedRepos,
}: EditGitHubConnectorConfigProps) {
	return (
		<div className="space-y-4">
			<h4 className="font-medium text-muted-foreground">Repository Selection & Access</h4>

			{/* Viewing Mode */}
			{editMode === "viewing" && (
				<div className="space-y-3 p-4 border rounded-md bg-muted/50">
					<FormLabel>Currently Indexed Repositories:</FormLabel>
					{currentSelectedRepos.length > 0 ? (
						<ul className="list-disc pl-5 text-sm">
							{currentSelectedRepos.map((repo) => (
								<li key={repo}>{repo}</li>
							))}
						</ul>
					) : (
						<p className="text-sm text-muted-foreground">(No repositories currently selected)</p>
					)}
					<Button
						type="button"
						variant="outline"
						size="sm"
						onClick={() => setEditMode("editing_repos")}
					>
						<Edit className="mr-2 h-4 w-4" /> Change Selection / Update PAT
					</Button>
					<FormDescription>
						To change repo selections or update the PAT, click above.
					</FormDescription>
				</div>
			)}

			{/* Editing Mode */}
			{editMode === "editing_repos" && (
				<div className="space-y-4 p-4 border rounded-md">
					{/* PAT Input */}
					<div className="flex items-end gap-4 p-4 border rounded-md bg-muted/90">
						<FormField
							control={patForm.control}
							name="github_pat"
							render={({ field }) => (
								<FormItem className="flex-grow">
									<FormLabel className="flex items-center gap-1">
										<KeyRound className="h-4 w-4" /> GitHub PAT
									</FormLabel>
									<FormControl>
										<Input type="password" placeholder="ghp_... or github_pat_..." {...field} />
									</FormControl>
									<FormDescription>
										Enter PAT to fetch/update repos or if you need to update the stored token.
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>
						<Button
							type="button"
							disabled={isFetchingRepos}
							size="sm"
							onClick={async () => {
								const isValid = await patForm.trigger("github_pat");
								if (isValid) {
									handleFetchRepositories(patForm.getValues());
								}
							}}
						>
							{isFetchingRepos ? (
								<Loader2 className="h-4 w-4 animate-spin" />
							) : (
								"Fetch Repositories"
							)}
						</Button>
					</div>

					{/* Repo List */}
					{isFetchingRepos && <Skeleton className="h-40 w-full" />}
					{!isFetchingRepos &&
						fetchedRepos !== null &&
						(fetchedRepos.length === 0 ? (
							<Alert variant="destructive">
								<CircleAlert className="h-4 w-4" />
								<AlertTitle>No Repositories Found</AlertTitle>
								<AlertDescription>Check PAT & permissions.</AlertDescription>
							</Alert>
						) : (
							<div className="space-y-2">
								<FormLabel>
									Select Repositories to Index ({newSelectedRepos.length} selected):
								</FormLabel>
								<div className="h-64 w-full rounded-md border p-4 overflow-y-auto">
									{fetchedRepos.map((repo) => (
										<div key={repo.id} className="flex items-center space-x-2 mb-2 py-1">
											<Checkbox
												id={`repo-${repo.id}`}
												checked={newSelectedRepos.includes(repo.full_name)}
												onCheckedChange={(checked) =>
													handleRepoSelectionChange(repo.full_name, !!checked)
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
							</div>
						))}
					<Button
						type="button"
						variant="ghost"
						size="sm"
						onClick={() => {
							setEditMode("viewing");
							setFetchedRepos(null);
							setNewSelectedRepos(currentSelectedRepos);
							patForm.reset({ github_pat: originalPat }); // Reset PAT form on cancel
						}}
					>
						Cancel Repo Change
					</Button>
				</div>
			)}
		</div>
	);
}
