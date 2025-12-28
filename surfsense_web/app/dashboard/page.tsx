"use client";

import { useAtomValue } from "jotai";
import { AlertCircle, Loader2, Plus, Search, Trash2, UserCheck, Users } from "lucide-react";
import { motion, type Variants } from "motion/react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { deleteSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { searchSpacesAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
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
import { Badge } from "@/components/ui/badge";
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
				<Card className="w-full max-w-[350px] bg-background/60 backdrop-blur-sm">
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
				<Card className="w-full max-w-[400px] bg-background/60 backdrop-blur-sm border-destructive/20">
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

	const {
		data: searchSpaces = [],
		isLoading: loading,
		error,
		refetch: refreshSearchSpaces,
	} = useAtomValue(searchSpacesAtom);
	const { mutateAsync: deleteSearchSpace } = useAtomValue(deleteSearchSpaceMutationAtom);

	const { data: user, isPending: isLoadingUser, error: userError } = useAtomValue(currentUserAtom);

	// Create user object for UserDropdown
	const customUser = {
		name: user?.email ? user.email.split("@")[0] : "User",
		email:
			user?.email ||
			(isLoadingUser ? "Loading..." : userError ? "Error loading user" : "Unknown User"),
		avatar: "/icon-128.png", // Default avatar
	};

	if (loading) return <LoadingScreen />;
	if (error) return <ErrorScreen message={error?.message || "Failed to load search spaces"} />;

	const handleDeleteSearchSpace = async (id: number) => {
		await deleteSearchSpace({ id });
		refreshSearchSpaces();
	};

	return (
		<motion.div
			className="container mx-auto py-6 md:py-10 px-4"
			initial="hidden"
			animate="visible"
			variants={containerVariants}
		>
			<motion.div className="flex flex-col space-y-4 md:space-y-6" variants={itemVariants}>
				<div className="flex flex-row items-center justify-between gap-2">
					<div className="flex flex-row items-center md:space-x-4">
						<Logo className="w-8 h-8 md:w-10 md:h-10 rounded-md shrink-0 hidden md:block" />
						<div className="flex flex-col space-y-0.5 md:space-y-2">
							<h1 className="text-xl md:text-4xl font-bold">{t("surfsense_dashboard")}</h1>
							<p className="text-sm md:text-base text-muted-foreground">{t("welcome_message")}</p>
						</div>
					</div>
					<div className="flex items-center space-x-2 md:space-x-3 shrink-0">
						<UserDropdown user={customUser} />
						<ThemeTogglerComponent />
					</div>
				</div>

				<div className="flex flex-col space-y-6 mt-6">
					<div className="flex justify-between items-center">
						<h2 className="text-lg md:text-2xl font-semibold">{t("your_search_spaces")}</h2>
						<motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
							<Link href="/dashboard/searchspaces">
								<Button className="h-8 md:h-10 text-[11px] md:text-sm px-3 md:px-4">
									<Plus className="mr-1 md:mr-2 h-3 w-3 md:h-4 md:w-4" />
									{t("create_search_space")}
								</Button>
							</Link>
						</motion.div>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
						{searchSpaces &&
							searchSpaces.length > 0 &&
							searchSpaces.map((space) => (
								<motion.div key={space.id} variants={itemVariants} className="aspect-4/3">
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
												<Link href={`/dashboard/${space.id}/new-chat`} key={space.id}>
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
												href={`/dashboard/${space.id}/new-chat`}
												key={space.id}
											>
												<div className="flex flex-1 flex-col justify-between p-1">
													<div>
														<div className="flex items-center gap-2">
															<h3 className="font-medium text-base md:text-lg">{space.name}</h3>
															{!space.is_owner && (
																<Badge variant="secondary" className="text-[10px] md:text-xs font-normal">
																	{t("shared")}
																</Badge>
															)}
														</div>
														<p className="mt-1 text-xs md:text-sm text-muted-foreground">
															{space.description}
														</p>
													</div>
													<div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
														<span>
															{t("created")} {formatDate(space.created_at)}
														</span>
														<div className="flex items-center gap-1">
															{space.is_owner ? (
																<UserCheck className="h-3.5 w-3.5" />
															) : (
																<Users className="h-3.5 w-3.5" />
															)}
															<span>{space.member_count}</span>
														</div>
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
								<h3 className="text-base md:text-lg font-medium mb-2">{t("no_spaces_found")}</h3>
								<p className="text-xs md:text-sm text-muted-foreground mb-6">{t("create_first_space")}</p>
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
											<Plus className="h-8 w-8 md:h-10 md:w-10 mb-2 md:mb-3 text-muted-foreground" />
											<span className="text-xs md:text-sm font-medium">{t("add_new_search_space")}</span>
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
