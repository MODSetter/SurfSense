"use client";

import { ArrowLeft, Shield, ShieldCheck, ShieldOff, Copy, Check, Download } from "lucide-react";
import Link from "next/link";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import { AdminGuard } from "@/components/AdminGuard";
import { DashboardHeader } from "@/components/DashboardHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
	DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUser } from "@/hooks";
import { AUTH_TOKEN_KEY } from "@/lib/constants";
import { authApiService } from "@/lib/apis/auth-api.service";
import { ValidationError } from "@/lib/error";

interface TwoFAStatus {
	enabled: boolean;
	has_backup_codes: boolean;
}

interface SetupData {
	secret: string;
	qr_code: string;
	uri: string;
}

export default function SecurityPage() {
	const { user, loading, error } = useUser();
	const [twoFAStatus, setTwoFAStatus] = useState<TwoFAStatus | null>(null);
	const [isLoadingStatus, setIsLoadingStatus] = useState(true);
	const [showSetupDialog, setShowSetupDialog] = useState(false);
	const [showDisableDialog, setShowDisableDialog] = useState(false);
	const [setupData, setSetupData] = useState<SetupData | null>(null);
	const [verificationCode, setVerificationCode] = useState("");
	const [disableCode, setDisableCode] = useState("");
	const [backupCodes, setBackupCodes] = useState<string[]>([]);
	const [showBackupCodes, setShowBackupCodes] = useState(false);
	const [copiedCode, setCopiedCode] = useState<string | null>(null);
	const [isProcessing, setIsProcessing] = useState(false);

	// Defensive: Safely handle user data, including null/undefined cases
	const customUser = {
		name: user?.email ? user.email.split("@")[0] : "User",
		email: user?.email || (error ? "Error loading user" : "Unknown User"),
		avatar: user?.avatar || "/icon-128.png",
	};

	// Fetch 2FA status
	useEffect(() => {
		if (user) {
			fetch2FAStatus();
		}
	}, [user]);

	const fetch2FAStatus = async () => {
		try {
			setIsLoadingStatus(true);
			const data = await authApiService.get2FAStatus();
			setTwoFAStatus(data);
		} catch (err) {
			console.error("Error fetching 2FA status:", err);
			toast.error("Failed to load 2FA status");
		} finally {
			setIsLoadingStatus(false);
		}
	};

	const handleEnableClick = async () => {
		setIsProcessing(true);
		try {
			const data = await authApiService.setup2FA();
			setSetupData(data);
			setShowSetupDialog(true);
		} catch (err) {
			console.error("Error starting 2FA setup:", err);
			if (err instanceof ValidationError) {
				toast.error(err.message);
			} else {
				toast.error("Failed to start 2FA setup");
			}
		} finally {
			setIsProcessing(false);
		}
	};

	const handleVerifySetup = async () => {
		if (!verificationCode.trim()) {
			toast.error("Please enter a verification code");
			return;
		}

		setIsProcessing(true);
		try {
			const data = await authApiService.verifySetup2FA({ code: verificationCode });
			if (data.backup_codes) {
				setBackupCodes(data.backup_codes);
				setShowBackupCodes(true);
			}
			setShowSetupDialog(false);
			setVerificationCode("");
			await fetch2FAStatus();
			toast.success("Two-Factor Authentication enabled successfully!");
		} catch (err) {
			console.error("Error verifying 2FA setup:", err);
			if (err instanceof ValidationError) {
				toast.error(err.message);
			} else {
				toast.error("Invalid verification code");
			}
		} finally {
			setIsProcessing(false);
		}
	};

	const handleDisable2FA = async () => {
		// Allow both TOTP codes (6 digits) and backup codes (XXXX-XXXX format)
		if (!disableCode.trim()) {
			toast.error("Please enter a code");
			return;
		}

		setIsProcessing(true);
		try {
			await authApiService.disable2FA({ code: disableCode });
			setShowDisableDialog(false);
			setDisableCode("");
			await fetch2FAStatus();
			toast.success("Two-Factor Authentication disabled successfully");
		} catch (err) {
			console.error("Error disabling 2FA:", err);
			if (err instanceof ValidationError) {
				toast.error(err.message);
			} else {
				toast.error("Invalid code");
			}
		} finally {
			setIsProcessing(false);
		}
	};

	const copyToClipboard = (text: string) => {
		navigator.clipboard.writeText(text);
		setCopiedCode(text);
		setTimeout(() => setCopiedCode(null), 2000);
		toast.success("Copied to clipboard");
	};

	const downloadBackupCodes = () => {
		const text = backupCodes.join("\n");
		const blob = new Blob([text], { type: "text/plain" });
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = "surfsense-2fa-backup-codes.txt";
		a.click();
		URL.revokeObjectURL(url);
		toast.success("Backup codes downloaded");
	};

	return (
		<AdminGuard>
			{(loading || isLoadingStatus) && (
				<div className="flex flex-col justify-center items-center min-h-screen">
					<div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
					<p className="text-muted-foreground">Loading Security Settings...</p>
				</div>
			)}

			{error && !loading && !isLoadingStatus && (
				<div className="container mx-auto py-10">
					<Alert variant="destructive">
						<AlertTitle>Error</AlertTitle>
						<AlertDescription>{error}</AlertDescription>
					</Alert>
				</div>
			)}

			{!loading && !isLoadingStatus && !error && (
			<div className="container mx-auto py-10">
			<div className="flex flex-col space-y-6">
				<DashboardHeader
					title="Security Settings"
					description="Manage your account security and two-factor authentication"
					user={customUser}
					isAdmin={user?.is_superuser ?? false}
				/>

				<div className="mb-4">
					<Link href="/dashboard">
						<Button variant="ghost" size="sm">
							<ArrowLeft className="mr-2 h-4 w-4" />
							Back to Dashboard
						</Button>
					</Link>
				</div>

				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2">
							<Shield className="h-5 w-5" />
							Two-Factor Authentication (2FA)
						</CardTitle>
						<CardDescription>
							Add an extra layer of security to your account by enabling two-factor authentication
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="flex items-center justify-between p-4 border rounded-lg">
							<div className="flex items-center gap-3">
								{twoFAStatus?.enabled ? (
									<ShieldCheck className="h-8 w-8 text-green-600" />
								) : (
									<ShieldOff className="h-8 w-8 text-muted-foreground" />
								)}
								<div>
									<p className="font-medium">2FA Status</p>
									<p className="text-sm text-muted-foreground">
										{twoFAStatus?.enabled
											? "Two-factor authentication is enabled"
											: "Two-factor authentication is not enabled"}
									</p>
								</div>
							</div>
							{twoFAStatus?.enabled ? (
								<Button variant="destructive" onClick={() => setShowDisableDialog(true)}>
									Disable 2FA
								</Button>
							) : (
								<Button onClick={handleEnableClick} disabled={isProcessing}>
									{isProcessing ? "Loading..." : "Enable 2FA"}
								</Button>
							)}
						</div>

						{/* Setup Dialog */}
						<Dialog open={showSetupDialog} onOpenChange={setShowSetupDialog}>
							<DialogContent className="sm:max-w-md">
								<DialogHeader>
									<DialogTitle>Setup Two-Factor Authentication</DialogTitle>
									<DialogDescription>
										Scan the QR code with your authenticator app (Google Authenticator, Authy, etc.)
									</DialogDescription>
								</DialogHeader>

								{setupData && (
									<div className="space-y-4">
										<div className="flex justify-center p-4 bg-white rounded-lg">
											<img
												src={`data:image/png;base64,${setupData.qr_code}`}
												alt="QR Code"
												className="w-64 h-64"
											/>
										</div>

										<div className="space-y-2">
											<Label>Manual Entry Key (if you can't scan)</Label>
											<div className="flex gap-2">
												<Input value={setupData.secret} readOnly className="font-mono" />
												<Button
													type="button"
													variant="outline"
													size="icon"
													onClick={() => copyToClipboard(setupData.secret)}
												>
													{copiedCode === setupData.secret ? (
														<Check className="h-4 w-4" />
													) : (
														<Copy className="h-4 w-4" />
													)}
												</Button>
											</div>
										</div>

										<div className="space-y-2">
											<Label htmlFor="verification-code">Enter 6-digit code from app</Label>
											<Input
												id="verification-code"
												type="text"
												inputMode="numeric"
												pattern="[0-9]{6}"
												maxLength={6}
												value={verificationCode}
												onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ""))}
												placeholder="000000"
												className="text-center text-lg tracking-widest"
											/>
										</div>
									</div>
								)}

								<DialogFooter>
									<Button
										type="button"
										variant="outline"
										onClick={() => {
											setShowSetupDialog(false);
											setVerificationCode("");
										}}
										disabled={isProcessing}
									>
										Cancel
									</Button>
									<Button
										onClick={handleVerifySetup}
										disabled={verificationCode.length !== 6 || isProcessing}
									>
										{isProcessing ? "Verifying..." : "Verify & Enable"}
									</Button>
								</DialogFooter>
							</DialogContent>
						</Dialog>

						{/* Disable Dialog */}
						<Dialog open={showDisableDialog} onOpenChange={setShowDisableDialog}>
							<DialogContent>
								<DialogHeader>
									<DialogTitle>Disable Two-Factor Authentication</DialogTitle>
									<DialogDescription>
										Enter your 6-digit code or a backup code to disable 2FA
									</DialogDescription>
								</DialogHeader>

								<div className="space-y-2">
									<Label htmlFor="disable-code">6-digit code or backup code</Label>
									<Input
										id="disable-code"
										type="text"
										value={disableCode}
										onChange={(e) => setDisableCode(e.target.value)}
										placeholder="Enter code"
										className="text-center"
									/>
								</div>

								<DialogFooter>
									<Button
										type="button"
										variant="outline"
										onClick={() => {
											setShowDisableDialog(false);
											setDisableCode("");
										}}
										disabled={isProcessing}
									>
										Cancel
									</Button>
									<Button
										variant="destructive"
										onClick={handleDisable2FA}
										disabled={disableCode.length === 0 || isProcessing}
									>
										{isProcessing ? "Disabling..." : "Disable 2FA"}
									</Button>
								</DialogFooter>
							</DialogContent>
						</Dialog>

						{/* Backup Codes Dialog */}
						<Dialog open={showBackupCodes} onOpenChange={setShowBackupCodes}>
							<DialogContent className="sm:max-w-md">
								<DialogHeader>
									<DialogTitle>Save Your Backup Codes</DialogTitle>
									<DialogDescription>
										Store these codes in a safe place. Each code can only be used once.
									</DialogDescription>
								</DialogHeader>

								<div className="space-y-4">
									<Alert>
										<ShieldCheck className="h-4 w-4" />
										<AlertTitle>Important!</AlertTitle>
										<AlertDescription>
											Save these backup codes now. You won't be able to see them again.
										</AlertDescription>
									</Alert>

									<div className="space-y-2 max-h-64 overflow-y-auto">
										{backupCodes.map((code, index) => (
											<div key={index} className="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-800 rounded">
												<code className="flex-1 font-mono text-sm">{code}</code>
												<Button
													type="button"
													variant="ghost"
													size="sm"
													onClick={() => copyToClipboard(code)}
												>
													{copiedCode === code ? (
														<Check className="h-4 w-4" />
													) : (
														<Copy className="h-4 w-4" />
													)}
												</Button>
											</div>
										))}
									</div>

									<Button
										type="button"
										onClick={downloadBackupCodes}
										className="w-full"
										variant="outline"
									>
										<Download className="h-4 w-4 mr-2" />
										Download Backup Codes
									</Button>
								</div>

								<DialogFooter>
									<Button
										onClick={() => {
											setShowBackupCodes(false);
											setBackupCodes([]);
										}}
										className="w-full"
									>
										I've Saved My Codes
									</Button>
								</DialogFooter>
							</DialogContent>
						</Dialog>
					</CardContent>
				</Card>
			</div>
		</div>
			)}
		</AdminGuard>
	);
}
