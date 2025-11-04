"use client";

import { AlertCircle, Loader2, Plus, Search, Trash2 } from "lucide-react";
import { motion, type Variants } from "motion/react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Logo } from "@/components/Logo";
import { ThemeTogglerComponent } from "@/components/theme/theme-toggle";
import { UserDropdown } from "@/components/UserDropdown";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Spotlight } from "@/components/ui/spotlight";
import { Tilt } from "@/components/ui/tilt";
import { useUser } from "@/hooks";
import { useSearchSpaces } from "@/hooks/use-search-spaces";

/**
 * Formats a date string into a readable format
 * @param dateString - The date string to format
 * @returns Formatted date string (e.g., "Jan 1, 2023")
 */
const formatDate = (dateString: string): string => {
	return new Date(dateString).toLocaleDateString("en-US", {
		year: "numeric",
		month: "short",
		day: "numeric",
	});
};

/**
 * Loading screen component with animation
 */
const LoadingScreen = () => {
	const t = useTranslations("dashboard");
	return (
		<div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
			<motion.div
				initial={{ opacity: 0, scale: 0.8 }}
				animate={{ opacity: 1, scale: 1 }}
				transition={{ duration: 0.5 }}
			>
				<Card className="w-[350px] bg-background/60 backdrop-blur-sm">
					<CardHeader className="pb-2">
						<CardTitle className="text-xl font-medium">{t("loading")}</CardTitle>
						<CardDescription>{t("fetching_spaces")}</CardDescription>
					</CardHeader>
					<CardContent className="flex justify-center py-6">
						<motion.div
							animate={{ rotate: 360 }}
							transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
						>
							<Loader2 className="h-12 w-12 text-primary" />
						</motion.div>
					</CardContent>
					<CardFooter className="border-t pt-4 text-sm text-muted-foreground">
						{t("may_take_moment")}
					</CardFooter>
				</Card>
			</motion.div>
		</div>
	);
};

/**
 * Error screen component with animation
 */
const ErrorScreen = ({ message }: { message: string }) => {
	const t = useTranslations("dashboard");
	const router = useRouter();

	return (
		<div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
			>
				<Card className="w-[400px] bg-background/60 backdrop-blur-sm border-destructive/20">
					<CardHeader className="pb-2">
						<div className="flex items-center gap-2">
							<AlertCircle className="h-5 w-5 text-destructive" />
							<CardTitle className="text-xl font-medium">{t("error")}</CardTitle>
						</div>
						<CardDescription>{t("something_wrong")}</CardDescription>
					</CardHeader>
					<CardContent>
						<Alert variant="destructive" className="bg-destructive/10 border-destructive/30">
							<AlertCircle className="h-4 w-4" />
							<AlertTitle>{t("error_details")}</AlertTitle>
							<AlertDescription className="mt-2">{message}</AlertDescription>
						</Alert>
					</CardContent>
					<CardFooter className="flex justify-end gap-2 border-t pt-4">
						<Button variant="outline" onClick={() => router.refresh()}>
							{t("try_again")}
						</Button>
						<Button onClick={() => router.push("/")}>{t("go_home")}</Button>
					</CardFooter>
				</Card>
			</motion.div>
		</div>
	);
};

const DashboardPage = () => {
	const t = useTranslations("dashboard");
	const tCommon = useTranslations("common");

	// Animation variants
	const containerVariants: Variants = {
		hidden: { opacity: 0 },
		visible: {
			opacity: 1,
			transition: {
				staggerChildren: 0.1,
			},
		},
	};

	const itemVariants: Variants = {
		hidden: { y: 20, opacity: 0 },
		visible: {
			y: 0,
			opacity: 1,
			transition: {
				type: "spring",
				stiffness: 300,
				damping: 24,
			},
		},
	};

	const { searchSpaces, loading, error, refreshSearchSpaces } = useSearchSpaces();

	// Fetch user details
	const { user, loading: isLoadingUser, error: userError } = useUser();

	// Create user object for UserDropdown
	const customUser = {
		name: user?.email ? user.email.split("@")[0] : "User",
		email:
			user?.email ||
			(isLoadingUser ? "Loading..." : userError ? "Error loading user" : "Unknown User"),
		avatar: "/icon-128.png", // Default avatar
	};

	if (loading) return <LoadingScreen />;
	if (error) return <ErrorScreen message={error} />;

	const handleDeleteSearchSpace = async (id: number) => {
		// Send DELETE request to the API
		try {
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${id}`,
				{
					method: "DELETE",
					headers: {
						Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
					},
				}
			);

			if (!response.ok) {
				toast.error("Failed to delete search space");
				throw new Error("Failed to delete search space");
			}

			// Refresh the search spaces list after successful deletion
			refreshSearchSpaces();
		} catch (error) {
			console.error("Error deleting search space:", error);
			toast.error("An error occurred while deleting the search space");
			return;
		}
		toast.success("Search space deleted successfully");
	};

	return (
		<motion.div
			className="container mx-auto py-10"
			initial="hidden"
			animate="visible"
			variants={containerVariants}
		>
			<motion.div className="flex flex-col space-y-6" variants={itemVariants}>
				<div className="flex flex-row space-x-4 justify-between">
					<div className="flex flex-row space-x-4">
						<Logo className="w-10 h-10 rounded-md" />
						<div className="flex flex-col space-y-2">
							<h1 className="text-4xl font-bold">{t("surfsense_dashboard")}</h1>
							<p className="text-muted-foreground">{t("welcome_message")}</p>
						</div>
					</div>
					<div className="flex items-center space-x-3">
						<UserDropdown user={customUser} />
						<ThemeTogglerComponent />
					</div>
				</div>

				<div className="flex flex-col space-y-6 mt-6">
					<div className="flex justify-between items-center">
						<h2 className="text-2xl font-semibold">{t("your_search_spaces")}</h2>
						<motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
							<Link href="/dashboard/searchspaces">
								<Button className="h-10">
									<Plus className="mr-2 h-4 w-4" />
									{t("create_search_space")}
								</Button>
							</Link>
						</motion.div>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
						{searchSpaces &&
							searchSpaces.length > 0 &&
							searchSpaces.map((space) => (
								<motion.div key={space.id} variants={itemVariants} className="aspect-[4/3]">
									<Tilt
										rotationFactor={6}
										isRevese
										springOptions={{
											stiffness: 26.7,
											damping: 4.1,
											mass: 0.2,
										}}
										className="group relative rounded-lg h-full"
									>
										<Spotlight
											className="z-10 from-blue-500/20 via-blue-300/10 to-blue-200/5 blur-2xl"
											size={248}
											springOptions={{
												stiffness: 26.7,
												damping: 4.1,
												mass: 0.2,
											}}
										/>
										<div className="flex flex-col h-full justify-between overflow-hidden rounded-xl border bg-muted/30 backdrop-blur-sm transition-all hover:border-primary/50">
											<div className="relative h-32 w-full overflow-hidden">
												<Link href={`/dashboard/${space.id}/documents`} key={space.id}>
													<Image
														src="https://images.unsplash.com/photo-1519389950473-47ba0277781c?ixlib=rb-4.0.3&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=1740&q=80"
														alt={space.name}
														className="h-full w-full object-cover grayscale duration-700 group-hover:grayscale-0"
														width={248}
														height={248}
													/>
													<div className="absolute inset-0 bg-gradient-to-t from-background/80 to-transparent" />
												</Link>
												<div className="absolute top-2 right-2">
													<div>
														<AlertDialog>
															<AlertDialogTrigger asChild>
																<Button
																	variant="ghost"
																	size="icon"
																	className="h-8 w-8 rounded-full bg-background/50 backdrop-blur-sm hover:bg-destructive/90 cursor-pointer"
																>
																	<Trash2 className="h-4 w-4" />
																</Button>
															</AlertDialogTrigger>
															<AlertDialogContent>
																<AlertDialogHeader>
																	<AlertDialogTitle>{t("delete_search_space")}</AlertDialogTitle>
																	<AlertDialogDescription>
																		{t("delete_space_confirm", { name: space.name })}
																	</AlertDialogDescription>
																</AlertDialogHeader>
																<AlertDialogFooter>
																	<AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
																	<AlertDialogAction
																		onClick={() => handleDeleteSearchSpace(space.id)}
																		className="bg-destructive hover:bg-destructive/90"
																	>
																		{tCommon("delete")}
																	</AlertDialogAction>
																</AlertDialogFooter>
															</AlertDialogContent>
														</AlertDialog>
													</div>
												</div>
											</div>
											<Link
												className="flex flex-1 flex-col p-4 cursor-pointer"
												href={`/dashboard/${space.id}/documents`}
												key={space.id}
											>
												<div className="flex flex-1 flex-col justify-between p-1">
													<div>
														<h3 className="font-medium text-lg">{space.name}</h3>
														<p className="mt-1 text-sm text-muted-foreground">
															{space.description}
														</p>
													</div>
													<div className="mt-4  text-xs text-muted-foreground">
														{/* <span>{space.title}</span> */}
														<span>
															{t("created")} {formatDate(space.created_at)}
														</span>
													</div>
												</div>
											</Link>
										</div>
									</Tilt>
								</motion.div>
							))}

						{searchSpaces.length === 0 && (
							<motion.div
								variants={itemVariants}
								className="col-span-full flex flex-col items-center justify-center p-12 text-center"
							>
								<div className="rounded-full bg-muted/50 p-4 mb-4">
									<Search className="h-8 w-8 text-muted-foreground" />
								</div>
								<h3 className="text-lg font-medium mb-2">{t("no_spaces_found")}</h3>
								<p className="text-muted-foreground mb-6">{t("create_first_space")}</p>
								<Link href="/dashboard/searchspaces">
									<Button>
										<Plus className="mr-2 h-4 w-4" />
										{t("create_search_space")}
									</Button>
								</Link>
							</motion.div>
						)}

						{searchSpaces.length > 0 && (
							<motion.div variants={itemVariants} className="aspect-[4/3]">
								<Tilt
									rotationFactor={6}
									isRevese
									springOptions={{
										stiffness: 26.7,
										damping: 4.1,
										mass: 0.2,
									}}
									className="group relative rounded-lg h-full"
								>
									<Link href="/dashboard/searchspaces" className="flex h-full">
										<div className="flex flex-col items-center justify-center h-full w-full rounded-xl border border-dashed bg-muted/10 hover:border-primary/50 transition-colors">
											<Plus className="h-10 w-10 mb-3 text-muted-foreground" />
											<span className="text-sm font-medium">{t("add_new_search_space")}</span>
										</div>
									</Link>
								</Tilt>
							</motion.div>
						)}
					</div>
				</div>
			</motion.div>
		</motion.div>
	);
};

export default DashboardPage;
