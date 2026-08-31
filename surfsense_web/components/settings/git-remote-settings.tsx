"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Github, Gitlab } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState, type FormEvent } from "react";
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
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { gitRemotesApiService } from "@/lib/apis/git-remotes-api.service";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { Spinner } from "../ui/spinner";

interface GitRemoteSettingsProps {
	workspaceId: number;
	githubInstallationId?: string;
	githubInstallations?: string;
	githubError?: string;
}

export function GitRemoteSettings({
	workspaceId,
	githubInstallationId,
	githubInstallations,
	githubError,
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
	const [sourcepath, setSourcepath] = useState("docs");
	const [busy, setBusy] = useState(false);
	const [selectedRepo, setSelectedRepo] = useState<{
		full_name: string;
		url: string;
		default_branch?: string;
	} | null>(null);
	const [branch, setBranch] = useState("main");

	const branchesQuery = useQuery({
		queryKey: cacheKeys.workspaces.githubBranches(
			workspaceId,
			githubInstallationId ?? "",
			selectedRepo?.full_name ?? ""
		),
		queryFn: () =>
			gitRemotesApiService.listGithubBranches(workspaceId, {
				installationId: githubInstallationId ?? "",
				fullName: selectedRepo?.full_name ?? "",
			}),
		enabled: gitNative && !!githubInstallationId && !!selectedRepo,
	});

	const foldersQuery = useQuery({
		queryKey: cacheKeys.workspaces.githubFolders(
			workspaceId,
			githubInstallationId ?? "",
			selectedRepo?.full_name ?? "",
			branch
		),
		queryFn: () =>
			gitRemotesApiService.listGithubFolders(workspaceId, {
				installationId: githubInstallationId ?? "",
				fullName: selectedRepo?.full_name ?? "",
				branch,
			}),
		enabled: gitNative && !!githubInstallationId && !!selectedRepo,
	});

	const installations = (githubInstallations ?? "")
		.split(",")
		.filter(Boolean)
		.map((pair) => {
			const [id, ...rest] = pair.split(":");
			return { id, account: rest.join(":") };
		});

	useEffect(() => {
		if (githubError === "oauth_failed") {
			toast.error(t("connected_repo_github_error"));
		}
	}, [githubError, t]);

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
			const { url } = await gitRemotesApiService.githubAuthorizeUrl(workspaceId);
			window.location.href = url;
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_github_error"));
			setBusy(false);
		}
	};

	const onGithubInstall = async () => {
		setBusy(true);
		try {
			const { url } = await gitRemotesApiService.githubInstallUrl(workspaceId);
			window.location.href = url;
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_github_error"));
			setBusy(false);
		}
	};

	const onConfirmGithub = async () => {
		if (!githubInstallationId || !selectedRepo) return;
		setBusy(true);
		try {
			await gitRemotesApiService.add(workspaceId, {
				provider: "github",
				url: selectedRepo.url,
				branch: branch.trim() || "main",
				installation_id: githubInstallationId,
				sourcepath: sourcepath.trim(),
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
				sourcepath: sourcepath.trim() || "docs",
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

	const onResolve = async (direction: "from_remote" | "from_local") => {
		setBusy(true);
		try {
			await gitRemotesApiService.resolve(workspaceId, direction);
			toast.success(t("connected_repo_push_queued"));
			await refresh();
		} catch (err) {
			toast.error(err instanceof Error ? err.message : t("connected_repo_resolve_error"));
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
					<div className="flex items-center justify-between gap-3">
						<span className="inline-flex items-center gap-1.5 text-sm font-medium">
							{remote.provider === "github" ? <Github size={15} /> : <Gitlab size={15} />}
							{remote.provider === "github" ? "GitHub" : "GitLab"}
						</span>
						{remote.last_error_code || remote.last_push_error ? (
							<Badge variant="destructive">{t("connected_repo_status_error")}</Badge>
						) : remote.last_pushed_revision ? (
							<Badge variant="secondary">{t("connected_repo_status_synced")}</Badge>
						) : (
							<Badge variant="outline" className="text-muted-foreground">
								{t("connected_repo_not_pushed")}
							</Badge>
						)}
					</div>
					<a
						href={remote.url}
						target="_blank"
						rel="noreferrer"
						className="font-mono text-sm break-all text-foreground hover:underline"
					>
						{remote.url}
					</a>
					<dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
						<dt className="text-muted-foreground">{t("connected_repo_branch_label")}</dt>
						<dd className="font-medium">{remote.branch}</dd>
						{remote.sourcepath != null ? (
							<>
								<dt className="text-muted-foreground">{t("connected_repo_sourcepath_label")}</dt>
								<dd className="font-mono">{remote.sourcepath || "/"}</dd>
							</>
						) : null}
						{remote.last_pushed_revision ? (
							<>
								<dt className="text-muted-foreground">{t("connected_repo_last_synced_label")}</dt>
								<dd className="font-mono text-xs">
									{remote.last_pushed_revision.slice(0, 12)}
									{remote.last_pushed_at
										? ` · ${new Date(remote.last_pushed_at).toLocaleString()}`
										: ""}
								</dd>
							</>
						) : null}
					</dl>
					{remote.last_error_code === "conflict" || remote.last_error_code === "need_direction" ? (
						<p className="text-xs text-destructive">
							{remote.last_error_code === "need_direction"
								? t("connected_repo_need_direction")
								: t("connected_repo_conflict")}
							{remote.last_conflict_paths ? ` ${remote.last_conflict_paths}` : ""}
						</p>
					) : remote.last_error_code ? (
						<p className="text-xs text-destructive">{remote.last_error_code}</p>
					) : remote.last_push_error ? (
						<p className="text-xs text-destructive">{remote.last_push_error}</p>
					) : null}
					<div className="flex flex-wrap gap-2">
						{remote.last_error_code === "conflict" ||
						remote.last_error_code === "need_direction" ? (
							<>
								<Button
									type="button"
									variant="secondary"
									size="sm"
									disabled={busy}
									onClick={() => onResolve("from_remote")}
								>
									{busy ? <Spinner size="sm" /> : t("connected_repo_use_remote")}
								</Button>
								<Button
									type="button"
									variant="secondary"
									size="sm"
									disabled={busy}
									onClick={() => onResolve("from_local")}
								>
									{busy ? <Spinner size="sm" /> : t("connected_repo_use_local")}
								</Button>
							</>
						) : (
							<Button type="button" variant="secondary" size="sm" disabled={busy} onClick={onRetry}>
								{busy ? <Spinner size="sm" /> : t("connected_repo_retry")}
							</Button>
						)}
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
			) : githubInstallationId && selectedRepo ? (
				<div className="flex flex-col gap-3 rounded-lg border p-4">
					<p className="text-sm font-medium">{selectedRepo.full_name}</p>
					<div className="flex flex-col gap-2">
						<Label htmlFor="github-branch">{t("connected_repo_branch_label")}</Label>
						<Select value={branch} onValueChange={setBranch}>
							<SelectTrigger id="github-branch">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{((branchesQuery.data ?? []).includes(branch)
									? (branchesQuery.data ?? [])
									: [branch, ...(branchesQuery.data ?? [])]
								).map((name) => (
									<SelectItem key={name} value={name}>
										{name}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</div>
					<div className="flex flex-col gap-2">
						<Label htmlFor="github-sourcepath">{t("connected_repo_sourcepath_label")}</Label>
						<Input
							id="github-sourcepath"
							list="github-folder-options"
							value={sourcepath}
							onChange={(e) => setSourcepath(e.target.value)}
							placeholder="docs"
						/>
						<datalist id="github-folder-options">
							{(foldersQuery.data ?? []).map((folder) => (
								<option key={folder} value={folder} />
							))}
						</datalist>
						<p className="text-xs text-muted-foreground">
							{foldersQuery.isLoading
								? t("connected_repo_folders_loading")
								: foldersQuery.isError
									? t("connected_repo_folders_error")
									: t("connected_repo_folder_hint")}
						</p>
					</div>
					<div className="flex gap-2">
						<Button type="button" size="sm" disabled={busy} onClick={onConfirmGithub}>
							{busy ? <Spinner size="sm" /> : t("connected_repo_connect_cta")}
						</Button>
						<Button
							type="button"
							variant="ghost"
							size="sm"
							disabled={busy}
							onClick={() => setSelectedRepo(null)}
						>
							{t("connected_repo_cancel")}
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
										onClick={() => {
											setSelectedRepo(repo);
											setBranch(repo.default_branch || "main");
										}}
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
			) : installations.length > 0 ? (
				<div className="flex flex-col gap-3 rounded-lg border p-4">
					<p className="text-sm">{t("connected_repo_choose_installation")}</p>
					<ul className="flex flex-col gap-1">
						{installations.map((inst) => (
							<li key={inst.id}>
								<Button
									type="button"
									variant="outline"
									size="sm"
									className="gap-1.5"
									onClick={() =>
										router.replace(`${settingsPath}?github_installation_id=${inst.id}`)
									}
								>
									<Github size={14} />
									{inst.account || inst.id}
								</Button>
							</li>
						))}
					</ul>
					<Button type="button" variant="ghost" size="sm" onClick={clearGithubQuery} className="w-fit">
						{t("connected_repo_cancel")}
					</Button>
				</div>
			) : githubError === "no_installation" ? (
				<div className="flex flex-col gap-3 rounded-lg border p-4">
					<p className="text-sm text-muted-foreground">{t("connected_repo_no_installation")}</p>
					<Button
						type="button"
						variant="secondary"
						size="sm"
						disabled={busy}
						onClick={onGithubInstall}
						className="w-fit"
					>
						{busy ? <Spinner size="sm" /> : t("connected_repo_install_cta")}
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
									<Label htmlFor="gitlab-sourcepath">{t("connected_repo_gitlab_sourcepath")}</Label>
									<Input
										id="gitlab-sourcepath"
										value={sourcepath}
										onChange={(e) => setSourcepath(e.target.value)}
										placeholder="docs"
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
