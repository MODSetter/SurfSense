"use client";

import { useAtom } from "jotai";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { type ExternalToast, toast } from "sonner";
import { registerMutationAtom } from "@/atoms/auth/auth-mutation.atoms";
import { Logo } from "@/components/Logo";
import { useRuntimeConfig } from "@/components/providers/runtime-config";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { useSession } from "@/hooks/use-session";
import { getAuthErrorDetails, isNetworkError, shouldRetry } from "@/lib/auth-errors";
import { AppError, ValidationError } from "@/lib/error";
import { trackRegistrationAttempt, trackRegistrationFailure } from "@/lib/posthog/events";

export default function RegisterPage() {
	const t = useTranslations("auth");
	const tCommon = useTranslations("common");
	const { authType } = useRuntimeConfig();
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [error, setError] = useState<{
		title: string | null;
		message: string | null;
	}>({
		title: null,
		message: null,
	});
	const router = useRouter();
	const session = useSession();
	const [{ mutateAsync: register, isPending: isRegistering }] = useAtom(registerMutationAtom);

	// Check authentication type and redirect if not LOCAL
	useEffect(() => {
		if (session.status === "authenticated") {
			router.replace("/dashboard");
			return;
		}
		if (authType !== "LOCAL") {
			router.push("/login");
		}
	}, [authType, router, session.status]);

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		submitForm();
	};

	const submitForm = async () => {
		// Form validation
		if (password !== confirmPassword) {
			setError({ title: t("password_mismatch"), message: t("passwords_no_match_desc") });
			toast.error(t("password_mismatch"), {
				description: t("passwords_no_match_desc"),
				duration: 4000,
			});
			return;
		}

		setError({ title: null, message: null }); // Clear any previous errors

		// Track registration attempt
		trackRegistrationAttempt();

		try {
			await register({
				email,
				password,
				is_active: true,
				is_superuser: false,
				is_verified: false,
			});

			// auth_registration_success is now emitted server-side
			// (UserManager.on_after_register) — authoritative vs. optimistic.

			// Success toast
			toast.success(t("register_success"), {
				description: t("redirecting_login"),
				duration: 2000,
			});

			// Small delay to show success message
			setTimeout(() => {
				router.push("/login?registered=true");
			}, 500);
		} catch (err) {
			if (err instanceof AppError) {
				switch (err.status) {
					case 403: {
						const friendlyMessage =
							"Registrations are currently closed. If you need access, contact your administrator.";
						trackRegistrationFailure("Registration disabled");
						setError({ title: "Registration is disabled", message: friendlyMessage });
						toast.error("Registration is disabled", {
							description: friendlyMessage,
							duration: 6000,
						});
						return;
					}
					default:
						break;
				}

				if (err instanceof ValidationError) {
					trackRegistrationFailure(err.message);
					setError({ title: err.name, message: err.message });
					toast.error(err.name, {
						description: err.message,
						duration: 6000,
					});
					return;
				}
			}

			// Use auth-errors utility to get proper error details
			let errorCode = "UNKNOWN_ERROR";

			if (err instanceof Error) {
				errorCode = err.message;
			} else if (isNetworkError(err)) {
				errorCode = "NETWORK_ERROR";
			}

			// Track registration failure
			trackRegistrationFailure(errorCode);

			// Get detailed error information from auth-errors utility
			const errorDetails = getAuthErrorDetails(errorCode);

			// Set persistent error display
			setError({ title: errorDetails.title, message: errorDetails.description });

			// Show error toast with conditional retry action
			const toastOptions: ExternalToast = {
				description: errorDetails.description,
				duration: 6000,
			};

			// Add retry action if the error is retryable
			if (shouldRetry(errorCode)) {
				toastOptions.action = {
					label: tCommon("retry"),
					onClick: () => submitForm(),
				};
			}

			toast.error(errorDetails.title, toastOptions);
		}
	};

	return (
		<div className="relative w-full overflow-hidden">
			<div className="mx-auto flex h-screen max-w-lg flex-col items-center justify-center px-6 md:px-0">
				<Logo priority className="h-14 w-14 rounded-md transition-all md:h-16 md:w-16" />
				<h1 className="mt-6 mb-2 text-center text-3xl leading-tight font-semibold tracking-tight text-balance md:text-4xl">
					{t("create_account")}
				</h1>
				<p className="text-center leading-relaxed text-pretty text-muted-foreground">
					{t("register_subtitle")}
				</p>

				<div className="mt-8 w-full max-w-md">
					<form onSubmit={handleSubmit} className="space-y-3 md:space-y-4">
						{/* Enhanced Error Display */}
						<AnimatePresence>
							{error?.title && (
								<motion.div
									initial={{ opacity: 0, y: -10, scale: 0.95 }}
									animate={{ opacity: 1, y: 0, scale: 1 }}
									exit={{ opacity: 0, y: -10, scale: 0.95 }}
									transition={{ duration: 0.3 }}
									className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-900 shadow-sm dark:border-red-900/30 dark:bg-red-900/20 dark:text-red-200"
								>
									<div className="flex items-start gap-3">
										<svg
											xmlns="http://www.w3.org/2000/svg"
											width="18"
											height="18"
											viewBox="0 0 24 24"
											fill="none"
											stroke="currentColor"
											strokeWidth="2"
											strokeLinecap="round"
											strokeLinejoin="round"
											className="shrink-0 mt-0.5 text-red-500 dark:text-red-400"
										>
											<title>Error Icon</title>
											<circle cx="12" cy="12" r="10" />
											<line x1="15" y1="9" x2="9" y2="15" />
											<line x1="9" y1="9" x2="15" y2="15" />
										</svg>
										<div className="flex-1 min-w-0">
											<p className="text-sm font-semibold mb-1">{error.title}</p>
											<p className="text-sm text-red-700 dark:text-red-300">{error.message}</p>
										</div>
										<Button
											variant="ghost"
											size="icon"
											onClick={() => {
												setError({ title: null, message: null });
											}}
											className="size-6 shrink-0 text-red-500 hover:bg-transparent hover:text-red-700 dark:text-red-400 dark:hover:text-red-200"
											aria-label="Dismiss error"
											type="button"
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												width="16"
												height="16"
												viewBox="0 0 24 24"
												fill="none"
												stroke="currentColor"
												strokeWidth="2"
												strokeLinecap="round"
												strokeLinejoin="round"
											>
												<title>Close</title>
												<line x1="18" y1="6" x2="6" y2="18" />
												<line x1="6" y1="6" x2="18" y2="18" />
											</svg>
										</Button>
									</div>
								</motion.div>
							)}
						</AnimatePresence>

						<div>
							<Label htmlFor="email">{t("email")}</Label>
							<Input
								id="email"
								type="email"
								autoComplete="email"
								required
								maxLength={254}
								placeholder="you@example.com"
								value={email}
								onChange={(e) => setEmail(e.target.value)}
								aria-invalid={!!error.title}
								className="mt-1"
								disabled={isRegistering}
							/>
						</div>

						<div>
							<Label htmlFor="password">{t("password")}</Label>
							<Input
								id="password"
								type="password"
								autoComplete="new-password"
								required
								placeholder="Enter your password"
								value={password}
								onChange={(e) => setPassword(e.target.value)}
								aria-invalid={!!error.title}
								className="mt-1"
								disabled={isRegistering}
							/>
						</div>

						<div>
							<Label htmlFor="confirmPassword">{t("confirm_password")}</Label>
							<Input
								id="confirmPassword"
								type="password"
								autoComplete="new-password"
								required
								placeholder="Confirm your password"
								value={confirmPassword}
								onChange={(e) => setConfirmPassword(e.target.value)}
								aria-invalid={!!error.title}
								className="mt-1"
								disabled={isRegistering}
							/>
						</div>

						<Button type="submit" size="lg" disabled={isRegistering} className="relative w-full">
							<span className={isRegistering ? "invisible" : ""}>{t("register")}</span>
							{isRegistering && (
								<span className="absolute inset-0 flex items-center justify-center gap-2">
									<Spinner size="sm" className="text-primary-foreground" />
								</span>
							)}
						</Button>
					</form>

					<div className="mt-4 text-center text-sm">
						<p className="text-muted-foreground">
							{t("already_have_account")}{" "}
							<Link href="/login" className="font-medium text-primary hover:text-primary/90">
								{t("sign_in")}
							</Link>
						</p>
					</div>
				</div>
			</div>
		</div>
	);
}
