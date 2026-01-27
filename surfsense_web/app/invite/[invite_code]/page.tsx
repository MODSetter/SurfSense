"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import {
	AlertCircle,
	ArrowRight,
	CheckCircle2,
	LogIn,
	Shield,
	Sparkles,
	Users,
	XCircle,
} from "lucide-react";
import { motion } from "motion/react";
import Image from "next/image";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { use, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { acceptInviteMutationAtom } from "@/atoms/invites/invites-mutation.atoms";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import type { AcceptInviteResponse } from "@/contracts/types/invites.types";
import { invitesApiService } from "@/lib/apis/invites-api.service";
import { getBearerToken } from "@/lib/auth-utils";
import {
	trackSearchSpaceInviteAccepted,
	trackSearchSpaceInviteDeclined,
	trackSearchSpaceUserAdded,
} from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";

export default function InviteAcceptPage() {
	const params = useParams();
	const router = useRouter();
	const inviteCode = params.invite_code as string;

	const { data: inviteInfo = null, isLoading: loading } = useQuery({
		queryKey: cacheKeys.invites.info(inviteCode),
		enabled: !!inviteCode,
		staleTime: 5 * 60 * 1000,
		queryFn: async () => {
			if (!inviteCode) return null;
			return invitesApiService.getInviteInfo({
				invite_code: inviteCode,
			});
		},
	});

	const { mutateAsync: acceptInviteMutation } = useAtomValue(acceptInviteMutationAtom);

	const acceptInvite = useCallback(async () => {
		if (!inviteCode) {
			toast.error("No invite code provided");
			return null;
		}

		try {
			const result = await acceptInviteMutation({ invite_code: inviteCode });
			return result;
		} catch (err: any) {
			toast.error(err.message || "Failed to accept invite");
			throw err;
		}
	}, [inviteCode, acceptInviteMutation]);

	const [accepting, setAccepting] = useState(false);
	const [accepted, setAccepted] = useState(false);
	const [acceptedData, setAcceptedData] = useState<AcceptInviteResponse | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [isLoggedIn, setIsLoggedIn] = useState<boolean | null>(null);

	// Check if user is logged in
	useEffect(() => {
		if (typeof window !== "undefined") {
			const token = getBearerToken();
			setIsLoggedIn(!!token);
		}
	}, []);

	const handleAccept = async () => {
		setAccepting(true);
		setError(null);
		try {
			const result = await acceptInvite();
			if (result) {
				setAccepted(true);
				setAcceptedData(result);

				// Track invite accepted and user added events
				trackSearchSpaceInviteAccepted(
					result.search_space_id,
					result.search_space_name,
					result.role_name
				);
				trackSearchSpaceUserAdded(
					result.search_space_id,
					result.search_space_name,
					result.role_name
				);
			}
		} catch (err: any) {
			setError(err.message || "Failed to accept invite");
		} finally {
			setAccepting(false);
		}
	};

	const handleDecline = () => {
		// Track invite declined event
		trackSearchSpaceInviteDeclined(inviteInfo?.search_space_name);
		router.push("/dashboard");
	};

	const handleLoginRedirect = () => {
		// Store the invite code to redirect back after login
		localStorage.setItem("pending_invite_code", inviteCode);
		// Save the current invite page URL so we can return after authentication
		localStorage.setItem("surfsense_redirect_path", `/invite/${inviteCode}`);
		// Redirect to login (we manually set the path above since invite pages need special handling)
		window.location.href = "/login";
	};

	// Check for pending invite after login
	useEffect(() => {
		if (isLoggedIn && typeof window !== "undefined") {
			const pendingInvite = localStorage.getItem("pending_invite_code");
			if (pendingInvite === inviteCode) {
				localStorage.removeItem("pending_invite_code");
				// Auto-accept the invite after redirect
				handleAccept();
			}
		}
	}, [isLoggedIn, inviteCode]);

	return (
		<div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-primary/5">
			{/* Background decoration */}
			<div className="absolute inset-0 overflow-hidden pointer-events-none">
				<div className="absolute -top-1/2 -right-1/2 w-full h-full bg-gradient-to-bl from-primary/10 via-transparent to-transparent rounded-full blur-3xl" />
				<div className="absolute -bottom-1/2 -left-1/2 w-full h-full bg-gradient-to-tr from-violet-500/10 via-transparent to-transparent rounded-full blur-3xl" />
			</div>

			<motion.div
				initial={{ opacity: 0, y: 20, scale: 0.95 }}
				animate={{ opacity: 1, y: 0, scale: 1 }}
				transition={{ duration: 0.5, ease: "easeOut" }}
				className="w-full max-w-md relative z-10"
			>
				<Card className="border-none shadow-2xl bg-card/80 backdrop-blur-xl">
					{loading || isLoggedIn === null ? (
						<CardContent className="flex flex-col items-center justify-center py-16">
							<motion.div
								animate={{ rotate: 360 }}
								transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
							>
								<Spinner size="xl" className="text-primary" />
							</motion.div>
							<p className="mt-4 text-muted-foreground">Loading invite details...</p>
						</CardContent>
					) : accepted && acceptedData ? (
						<>
							<CardHeader className="text-center pb-4">
								<motion.div
									initial={{ scale: 0 }}
									animate={{ scale: 1 }}
									transition={{ type: "spring", stiffness: 200, damping: 15 }}
									className="mx-auto mb-4 h-20 w-20 rounded-full bg-gradient-to-br from-emerald-500/20 to-emerald-500/5 flex items-center justify-center ring-4 ring-emerald-500/20"
								>
									<CheckCircle2 className="h-10 w-10 text-emerald-500" />
								</motion.div>
								<CardTitle className="text-2xl">Welcome to the team!</CardTitle>
								<CardDescription>
									You've successfully joined {acceptedData.search_space_name}
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="bg-muted/50 rounded-lg p-4 space-y-3">
									<div className="flex items-center gap-3">
										<div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
											<Users className="h-5 w-5 text-primary" />
										</div>
										<div>
											<p className="font-medium">{acceptedData.search_space_name}</p>
											<p className="text-sm text-muted-foreground">Search Space</p>
										</div>
									</div>
									<div className="flex items-center gap-3">
										<div className="h-10 w-10 rounded-lg bg-violet-500/10 flex items-center justify-center">
											<Shield className="h-5 w-5 text-violet-500" />
										</div>
										<div>
											<p className="font-medium">{acceptedData.role_name}</p>
											<p className="text-sm text-muted-foreground">Your Role</p>
										</div>
									</div>
								</div>
							</CardContent>
							<CardFooter>
								<Button
									className="w-full gap-2"
									onClick={() => router.push(`/dashboard/${acceptedData.search_space_id}`)}
								>
									Go to Search Space
									<ArrowRight className="h-4 w-4" />
								</Button>
							</CardFooter>
						</>
					) : !inviteInfo?.is_valid ? (
						<>
							<CardHeader className="text-center pb-4">
								<motion.div
									initial={{ scale: 0 }}
									animate={{ scale: 1 }}
									transition={{ type: "spring", stiffness: 200, damping: 15 }}
									className="mx-auto mb-4 h-20 w-20 rounded-full bg-gradient-to-br from-destructive/20 to-destructive/5 flex items-center justify-center ring-4 ring-destructive/20"
								>
									<XCircle className="h-10 w-10 text-destructive" />
								</motion.div>
								<CardTitle className="text-2xl">Invalid Invite</CardTitle>
								<CardDescription>
									{inviteInfo?.message || "This invite link is no longer valid"}
								</CardDescription>
							</CardHeader>
							<CardContent className="text-center">
								<p className="text-sm text-muted-foreground">
									The invite may have expired, reached its maximum uses, or been revoked by the
									owner.
								</p>
							</CardContent>
							<CardFooter>
								<Button
									variant="outline"
									className="w-full"
									onClick={() => router.push("/dashboard")}
								>
									Go to Dashboard
								</Button>
							</CardFooter>
						</>
					) : !isLoggedIn ? (
						<>
							<CardHeader className="text-center pb-4">
								<motion.div
									initial={{ scale: 0 }}
									animate={{ scale: 1 }}
									transition={{ type: "spring", stiffness: 200, damping: 15 }}
									className="mx-auto mb-4 h-20 w-20 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center ring-4 ring-primary/20"
								>
									<Sparkles className="h-10 w-10 text-primary" />
								</motion.div>
								<CardTitle className="text-2xl">You're Invited!</CardTitle>
								<CardDescription>
									Sign in to join {inviteInfo?.search_space_name || "this search space"}
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="bg-muted/50 rounded-lg p-4 space-y-3">
									<div className="flex items-center gap-3">
										<div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
											<Users className="h-5 w-5 text-primary" />
										</div>
										<div>
											<p className="font-medium">{inviteInfo?.search_space_name}</p>
											<p className="text-sm text-muted-foreground">Search Space</p>
										</div>
									</div>
									{inviteInfo?.role_name && (
										<div className="flex items-center gap-3">
											<div className="h-10 w-10 rounded-lg bg-violet-500/10 flex items-center justify-center">
												<Shield className="h-5 w-5 text-violet-500" />
											</div>
											<div>
												<p className="font-medium">{inviteInfo.role_name}</p>
												<p className="text-sm text-muted-foreground">Role you'll receive</p>
											</div>
										</div>
									)}
								</div>
							</CardContent>
							<CardFooter>
								<Button className="w-full gap-2" onClick={handleLoginRedirect}>
									<LogIn className="h-4 w-4" />
									Sign in to Accept
								</Button>
							</CardFooter>
						</>
					) : (
						<>
							<CardHeader className="text-center pb-4">
								<motion.div
									initial={{ scale: 0 }}
									animate={{ scale: 1 }}
									transition={{ type: "spring", stiffness: 200, damping: 15 }}
									className="mx-auto mb-4 h-20 w-20 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center ring-4 ring-primary/20"
								>
									<Sparkles className="h-10 w-10 text-primary" />
								</motion.div>
								<CardTitle className="text-2xl">You're Invited!</CardTitle>
								<CardDescription>
									Accept this invite to join {inviteInfo?.search_space_name || "this search space"}
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="bg-muted/50 rounded-lg p-4 space-y-3">
									<div className="flex items-center gap-3">
										<div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
											<Users className="h-5 w-5 text-primary" />
										</div>
										<div>
											<p className="font-medium">{inviteInfo?.search_space_name}</p>
											<p className="text-sm text-muted-foreground">Search Space</p>
										</div>
									</div>
									{inviteInfo?.role_name && (
										<div className="flex items-center gap-3">
											<div className="h-10 w-10 rounded-lg bg-violet-500/10 flex items-center justify-center">
												<Shield className="h-5 w-5 text-violet-500" />
											</div>
											<div>
												<p className="font-medium">{inviteInfo.role_name}</p>
												<p className="text-sm text-muted-foreground">Role you'll receive</p>
											</div>
										</div>
									)}
								</div>

								{error && (
									<motion.div
										initial={{ opacity: 0, y: -10 }}
										animate={{ opacity: 1, y: 0 }}
										className="flex items-center gap-2 p-3 bg-destructive/10 text-destructive rounded-lg text-sm"
									>
										<AlertCircle className="h-4 w-4 shrink-0" />
										{error}
									</motion.div>
								)}
							</CardContent>
							<CardFooter className="flex gap-2">
								<Button variant="outline" className="flex-1" onClick={handleDecline}>
									Cancel
								</Button>
								<Button className="flex-1 gap-2" onClick={handleAccept} disabled={accepting}>
									{accepting ? (
										<>
											<Spinner size="sm" />
											Accepting...
										</>
									) : (
										<>
											<CheckCircle2 className="h-4 w-4" />
											Accept Invite
										</>
									)}
								</Button>
							</CardFooter>
						</>
					)}
				</Card>

				{/* Branding */}
				<motion.div
					initial={{ opacity: 0 }}
					animate={{ opacity: 1 }}
					transition={{ delay: 0.3 }}
					className="mt-6 text-center"
				>
					<Link
						href="/"
						className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
					>
						<Image src="/icon-128.svg" alt="SurfSense" width={24} height={24} className="rounded" />
						<span className="text-sm font-medium">SurfSense</span>
					</Link>
				</motion.div>
			</motion.div>
		</div>
	);
}
