"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Github, Gitlab } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { gitRemotesApiService } from "@/lib/apis/git-remotes-api.service";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { Spinner } from "../ui/spinner";

interface GitRemoteSettingsProps {
	workspaceId: number;
	githubInstallationId?: string;
}

export function GitRemoteSettings({
	workspaceId,
	githubInstallationId,
}: GitRemoteSettingsProps) {
	const t = useTranslations("workspaceSettings");
	const router = useRouter();
	const queryClient = useQueryClient();
	const workspaceQuery = useQuery({
		queryKey: cacheKeys.workspaces.detail(workspaceId.toString()),
		queryFn: () => workspacesApiService.getWorkspace({ id: workspaceId }),
		enabled: !!workspaceId,
	});
	const gitNative = workspaceQuery.data?.knowledge_store_enabled === true;
	const remotesQuery = useQuery({
		queryKey: cacheKeys.workspaces.gitRemotes(workspaceId),
		queryFn: () => gitRemotesApiService.list(workspaceId),
		enabled: gitNative,
	});
	const reposQuery = useQuery({
		queryKey: cacheKeys.workspaces.githubRepos(workspaceId, githubInstallationId ?? ""),
		queryFn: () => gitRemotesApiService.listGithubRepos(workspaceId, githubInstallationId ?? ""),
		enabled: gitNative && !!githubInstallationId,
	});

	const [gitlabUrl, setGitlabUrl] = useState("");
	const [gitlabBranch, setGitlabBranch] = useState("main");
	const [gitlabToken, setGitlabToken] = useState("");
	const [busy, setBusy] = useState(false);

	const remote = remotesQuery.data?.[0];
	const settingsPath = `/dashboard/${workspaceId}/workspace-settings/git-remote`;
	const clearGithubQuery = () => {
		router.replace(settingsPath);
	};

	const refresh = () =>
		queryClient.invalidateQueries({ queryKey: cacheKeys.workspaces.gitRemotes(workspaceId) });

	const onGithubConnect = async () => {
		setBusy(true);
		try {
			const { url } = await gitRemotesApiService.githubInstallUrl(workspaceId);
			window.location.href = url;
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_github_error"));
			setBusy(false);
		}
	};

	const onPickGithubRepo = async (url: string) => {
		if (!githubInstallationId) return;
		setBusy(true);
		try {
			await gitRemotesApiService.add(workspaceId, {
				provider: "github",
				url,
				branch: "main",
				installation_id: githubInstallationId,
			});
			toast.success(t("connected_repo_github_connected"));
			await refresh();
			clearGithubQuery();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_github_add_error"));
		} finally {
			setBusy(false);
		}
	};

	const onGitlabConnect = async (e: FormEvent) => {
		e.preventDefault();
		setBusy(true);
		try {
			await gitRemotesApiService.add(workspaceId, {
				provider: "gitlab",
				url: gitlabUrl.trim(),
				branch: gitlabBranch.trim() || "main",
				token: gitlabToken.trim(),
			});
			toast.success(t("connected_repo_gitlab_connected"));
			setGitlabToken("");
			await refresh();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_gitlab_add_error"));
		} finally {
			setBusy(false);
		}
	};

	const onDisconnect = async () => {
		setBusy(true);
		try {
			await gitRemotesApiService.remove(workspaceId);
			toast.success(t("connected_repo_disconnected"));
			await refresh();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_disconnect_error"));
		} finally {
			setBusy(false);
		}
	};

	const onRetry = async () => {
		setBusy(true);
		try {
			await gitRemotesApiService.retryPush(workspaceId);
			toast.success(t("connected_repo_push_queued"));
			await refresh();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_retry_error"));
		} finally {
			setBusy(false);
		}
	};

	if (workspaceQuery.isLoading) {
		return (
			<div className="flex flex-col gap-4">
				<Skeleton className="h-4 w-2/3" />
				<Skeleton className="h-10 w-40" />
			</div>
		);
	}

	if (!gitNative) {
		return <p className="text-sm text-muted-foreground">{t("connected_repo_not_native")}</p>;
	}

	return (
		<div className="flex flex-col gap-6">
			<p className="text-sm text-muted-foreground">{t("connected_repo_description")}</p>

			{remotesQuery.isLoading ? (
				<Skeleton className="h-24 w-full" />
			) : remote ? (
				<div className="flex flex-col gap-4 rounded-lg border p-4">
					<div className="flex flex-col gap-2">
						<Badge variant="secondary" className="capitalize">
							{remote.provider === "github" ? "GitHub" : "GitLab"}
						</Badge>
						<p className="text-sm break-all">{remote.url}</p>
						<p className="text-xs text-muted-foreground">{t("connected_repo_branch", { branch: remote.branch })}</p>
					</div>
					{remote.last_pushed_revision ? (
						<p className="text-xs text-muted-foreground font-mono">
							{t("connected_repo_last_pushed", {
								sha: remote.last_pushed_revision.slice(0, 12),
								when: remote.last_pushed_at
									? ` · ${new Date(remote.last_pushed_at).toLocaleString()}`
									: "",
							})}
						</p>
					) : (
						<p className="text-xs text-muted-foreground">{t("connected_repo_not_pushed")}</p>
					)}
					{remote.last_push_error ? (
						<p className="text-xs text-destructive">{remote.last_push_error}</p>
					) : null}
					<div className="flex flex-wrap gap-2">
						<Button type="button" variant="secondary" size="sm" disabled={busy} onClick={onRetry}>
							{busy ? <Spinner size="sm" /> : t("connected_repo_retry")}
						</Button>
						<Button
							type="button"
							variant="outline"
							size="sm"
							disabled={busy}
							onClick={onDisconnect}
						>
							{t("connected_repo_disconnect")}
						</Button>
					</div>
				</div>
			) : githubInstallationId ? (
				<div className="flex flex-col gap-3 rounded-lg border p-4">
					<p className="text-sm">{t("connected_repo_pick")}</p>
					{reposQuery.isLoading ? (
						<Skeleton className="h-10 w-full" />
					) : (reposQuery.data ?? []).length === 0 ? (
						<p className="text-xs text-muted-foreground">{t("connected_repo_no_repos")}</p>
					) : (
						<ul className="flex flex-col gap-1">
							{(reposQuery.data ?? []).map((repo) => (
								<li key={repo.full_name}>
									<Button
										type="button"
										variant="outline"
										size="sm"
										disabled={busy}
										onClick={() => onPickGithubRepo(repo.url)}
									>
										{repo.full_name}
									</Button>
								</li>
							))}
						</ul>
					)}
					<Button type="button" variant="ghost" size="sm" onClick={clearGithubQuery} className="w-fit">
						{t("connected_repo_cancel")}
					</Button>
				</div>
			) : (
				<Accordion type="single" collapsible defaultValue="github" className="rounded-lg border">
					<AccordionItem value="github" className="px-4">
						<AccordionTrigger className="hover:no-underline">
							<span className="flex items-center gap-2">
								<Github />
								GitHub
							</span>
						</AccordionTrigger>
						<AccordionContent>
							<div className="flex flex-col gap-3">
								<p className="text-muted-foreground">{t("connected_repo_github_blurb")}</p>
								<Button
									type="button"
									variant="secondary"
									size="sm"
									disabled={busy}
									onClick={onGithubConnect}
									className="w-fit"
								>
									{busy ? <Spinner size="sm" /> : t("connected_repo_github_cta")}
								</Button>
							</div>
						</AccordionContent>
					</AccordionItem>
					<AccordionItem value="gitlab" className="px-4">
						<AccordionTrigger className="hover:no-underline">
							<span className="flex items-center gap-2">
								<Gitlab />
								GitLab
							</span>
						</AccordionTrigger>
						<AccordionContent>
							<form onSubmit={onGitlabConnect} className="flex flex-col gap-3">
								<p className="text-muted-foreground">{t("connected_repo_gitlab_blurb")}</p>
								<div className="flex flex-col gap-2">
									<Label htmlFor="gitlab-url">{t("connected_repo_gitlab_url")}</Label>
									<Input
										id="gitlab-url"
										type="url"
										placeholder="https://gitlab.com/group/project.git"
										value={gitlabUrl}
										onChange={(e) => setGitlabUrl(e.target.value)}
										required
									/>
								</div>
								<div className="flex flex-col gap-2">
									<Label htmlFor="gitlab-branch">{t("connected_repo_gitlab_branch")}</Label>
									<Input
										id="gitlab-branch"
										value={gitlabBranch}
										onChange={(e) => setGitlabBranch(e.target.value)}
									/>
								</div>
								<div className="flex flex-col gap-2">
									<Label htmlFor="gitlab-token">{t("connected_repo_gitlab_token")}</Label>
									<Input
										id="gitlab-token"
										type="password"
										autoComplete="off"
										value={gitlabToken}
										onChange={(e) => setGitlabToken(e.target.value)}
										required
									/>
								</div>
								<Button type="submit" variant="secondary" size="sm" disabled={busy} className="w-fit">
									{busy ? <Spinner size="sm" /> : t("connected_repo_gitlab_cta")}
								</Button>
							</form>
						</AccordionContent>
					</AccordionItem>
				</Accordion>
			)}
		</div>
	);
}
