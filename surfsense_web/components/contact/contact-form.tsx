"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { IconMailFilled } from "@tabler/icons-react";
import { motion } from "motion/react";
import Image from "next/image";
import Link from "next/link";
import type React from "react";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { cn } from "@/lib/utils";

// Define validation schema matching the database schema
const contactFormSchema = z.object({
	name: z.string().min(1, "Name is required").max(255, "Name is too long"),
	email: z.string().email("Invalid email address").max(255, "Email is too long"),
	company: z.string().min(1, "Company is required").max(255, "Company name is too long"),
	message: z.string().optional().default(""),
});

type ContactFormData = z.infer<typeof contactFormSchema>;

export function ContactFormGridWithDetails() {
	const [isSubmitting, setIsSubmitting] = useState(false);

	const {
		register,
		handleSubmit,
		formState: { errors },
		reset,
	} = useForm<ContactFormData>({
		resolver: zodResolver(contactFormSchema),
	});

	const onSubmit = async (data: ContactFormData) => {
		setIsSubmitting(true);

		try {
			const response = await fetch("/api/contact", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify(data),
			});

			const result = await response.json();

			if (response.ok) {
				toast.success("Message sent successfully!", {
					description: "We will get back to you as soon as possible.",
				});
				reset();
			} else {
				toast.error("Failed to send message", {
					description: result.message || "Please try again later.",
				});
			}
		} catch (error) {
			console.error("Error submitting form:", error);
			toast.error("Something went wrong", {
				description: "Please try again later.",
			});
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div className="mx-auto grid w-full max-w-7xl grid-cols-1 gap-10 px-4 py-10 md:px-6 md:py-20 lg:grid-cols-2">
			<div className="relative flex flex-col items-center overflow-hidden lg:items-start">
				<div className="flex items-start justify-start">
					<FeatureIconContainer className="flex items-center justify-center overflow-hidden">
						<IconMailFilled className="h-6 w-6 text-blue-500" />
					</FeatureIconContainer>
				</div>
				<h2 className="mt-9 bg-gradient-to-b from-neutral-800 to-neutral-900 bg-clip-text text-left text-xl font-bold text-transparent md:text-3xl lg:text-5xl dark:from-neutral-200 dark:to-neutral-300">
					Contact
				</h2>
				<p className="mt-8 max-w-lg text-center text-base text-neutral-600 md:text-left dark:text-neutral-400">
					We'd love to Hear From You.
				</p>

				<div className="mt-10 hidden flex-col items-center gap-4 md:flex-row lg:flex">
					<Link
						href="mailto:rohan@surfsense.com"
						className="text-sm text-neutral-500 dark:text-neutral-400"
					>
						rohan@surfsense.com
					</Link>
					<div className="h-1 w-1 rounded-full bg-neutral-500 dark:bg-neutral-400" />

					<Link
						href="https://cal.com/mod-surfsense"
						className="text-sm text-neutral-500 dark:text-neutral-400"
					>
						https://cal.com/mod-surfsense
					</Link>
				</div>
				<div className="div relative mt-20 flex w-[600px] flex-shrink-0 -translate-x-10 items-center justify-center [perspective:800px] [transform-style:preserve-3d] sm:-translate-x-0 lg:-translate-x-32">
					<Pin className="h-30 w-85 top-0 left-0" />

					<Image
						src="/contact/world.svg"
						width={500}
						height={500}
						alt="world map"
						className="[transform:rotateX(45deg)_translateZ(0px)] dark:invert dark:filter"
					/>
				</div>
			</div>
			<form
				onSubmit={handleSubmit(onSubmit)}
				className="relative mx-auto flex w-full max-w-2xl flex-col items-start gap-4 overflow-hidden rounded-3xl bg-gradient-to-b from-gray-100 to-gray-200 p-4 sm:p-10 dark:from-neutral-900 dark:to-neutral-950"
			>
				<Grid size={20} />
				<div className="relative z-20 mb-4 w-full">
					<label
						className="mb-2 inline-block text-sm font-medium text-neutral-600 dark:text-neutral-300"
						htmlFor="name"
					>
						Full name
					</label>
					<input
						id="name"
						type="text"
						placeholder="John Doe"
						{...register("name")}
						className={cn(
							"shadow-input h-10 w-full rounded-md border bg-white pl-4 text-sm text-neutral-700 placeholder-neutral-500 outline-none focus:ring-2 focus:ring-neutral-800 focus:outline-none active:outline-none dark:border-neutral-800 dark:bg-neutral-800 dark:text-white",
							errors.name ? "border-red-500" : "border-transparent"
						)}
					/>
					{errors.name && <p className="mt-1 text-xs text-red-500">{errors.name.message}</p>}
				</div>
				<div className="relative z-20 mb-4 w-full">
					<label
						className="mb-2 inline-block text-sm font-medium text-neutral-600 dark:text-neutral-300"
						htmlFor="email"
					>
						Email Address
					</label>
					<input
						id="email"
						type="email"
						placeholder="john.doe@example.com"
						{...register("email")}
						className={cn(
							"shadow-input h-10 w-full rounded-md border bg-white pl-4 text-sm text-neutral-700 placeholder-neutral-500 outline-none focus:ring-2 focus:ring-neutral-800 focus:outline-none active:outline-none dark:border-neutral-800 dark:bg-neutral-800 dark:text-white",
							errors.email ? "border-red-500" : "border-transparent"
						)}
					/>
					{errors.email && <p className="mt-1 text-xs text-red-500">{errors.email.message}</p>}
				</div>
				<div className="relative z-20 mb-4 w-full">
					<label
						className="mb-2 inline-block text-sm font-medium text-neutral-600 dark:text-neutral-300"
						htmlFor="company"
					>
						Company
					</label>
					<input
						id="company"
						type="text"
						placeholder="Example Inc."
						{...register("company")}
						className={cn(
							"shadow-input h-10 w-full rounded-md border bg-white pl-4 text-sm text-neutral-700 placeholder-neutral-500 outline-none focus:ring-2 focus:ring-neutral-800 focus:outline-none active:outline-none dark:border-neutral-800 dark:bg-neutral-800 dark:text-white",
							errors.company ? "border-red-500" : "border-transparent"
						)}
					/>
					{errors.company && <p className="mt-1 text-xs text-red-500">{errors.company.message}</p>}
				</div>
				<div className="relative z-20 mb-4 w-full">
					<label
						className="mb-2 inline-block text-sm font-medium text-neutral-600 dark:text-neutral-300"
						htmlFor="message"
					>
						Message <span className="text-neutral-400 text-xs font-normal">(optional)</span>
					</label>
					<textarea
						id="message"
						rows={5}
						placeholder="Type your message here"
						{...register("message")}
						className={cn(
							"shadow-input w-full rounded-md border bg-white pt-4 pl-4 text-sm text-neutral-700 placeholder-neutral-500 outline-none focus:ring-2 focus:ring-neutral-800 focus:outline-none active:outline-none dark:border-neutral-800 dark:bg-neutral-800 dark:text-white",
							errors.message ? "border-red-500" : "border-transparent"
						)}
					/>
					{errors.message && <p className="mt-1 text-xs text-red-500">{errors.message.message}</p>}
				</div>
				<button
					type="submit"
					disabled={isSubmitting}
					className="relative z-10 flex items-center justify-center rounded-md border border-transparent bg-neutral-800 px-4 py-2 text-sm font-medium text-white shadow-[0px_1px_0px_0px_#FFFFFF20_inset] transition duration-200 hover:bg-neutral-900 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
				>
					{isSubmitting ? "Submitting..." : "Submit"}
				</button>
			</form>
		</div>
	);
}

const Pin = ({ className }: { className?: string }) => {
	return (
		<motion.div
			style={{ transform: "translateZ(1px)" }}
			className={cn(
				"pointer-events-none absolute z-[60] flex h-40 w-96 items-center justify-center opacity-100 transition duration-500",
				className
			)}
		>
			<div className="h-full w-full">
				<div className="absolute inset-x-0 top-0 z-20 mx-auto inline-block w-fit rounded-lg bg-neutral-200 px-2 py-1 text-xs font-normal text-neutral-700 dark:bg-neutral-800 dark:text-white">
					We are here
					<span className="absolute -bottom-0 left-[1.125rem] h-px w-[calc(100%-2.25rem)] bg-gradient-to-r from-blue-400/0 via-blue-400/90 to-blue-400/0 transition-opacity duration-500"></span>
				</div>

				<div
					style={{
						perspective: "800px",
						transform: "rotateX(70deg) translateZ(0px)",
					}}
					className="absolute top-1/2 left-1/2 mt-4 ml-[0.09375rem] -translate-x-1/2 -translate-y-1/2"
				>
					<>
						<motion.div
							initial={{ opacity: 0, scale: 0 }}
							animate={{
								opacity: [0, 1, 0.5, 0],
								scale: 1,
							}}
							transition={{ duration: 6, repeat: Infinity, delay: 0 }}
							className="absolute top-1/2 left-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-[50%] bg-sky-500/[0.08] shadow-[0_8px_16px_rgb(0_0_0/0.4)] dark:bg-sky-500/[0.2]"
						></motion.div>
						<motion.div
							initial={{ opacity: 0, scale: 0 }}
							animate={{
								opacity: [0, 1, 0.5, 0],
								scale: 1,
							}}
							transition={{ duration: 6, repeat: Infinity, delay: 2 }}
							className="absolute top-1/2 left-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-[50%] bg-sky-500/[0.08] shadow-[0_8px_16px_rgb(0_0_0/0.4)] dark:bg-sky-500/[0.2]"
						></motion.div>
						<motion.div
							initial={{ opacity: 0, scale: 0 }}
							animate={{
								opacity: [0, 1, 0.5, 0],
								scale: 1,
							}}
							transition={{ duration: 6, repeat: Infinity, delay: 4 }}
							className="absolute top-1/2 left-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-[50%] bg-sky-500/[0.08] shadow-[0_8px_16px_rgb(0_0_0/0.4)] dark:bg-sky-500/[0.2]"
						></motion.div>
					</>
				</div>

				<>
					<motion.div className="absolute right-1/2 bottom-1/2 h-20 w-px translate-y-[14px] bg-gradient-to-b from-transparent to-blue-500 blur-[2px]" />
					<motion.div className="absolute right-1/2 bottom-1/2 h-20 w-px translate-y-[14px] bg-gradient-to-b from-transparent to-blue-500" />
					<motion.div className="absolute right-1/2 bottom-1/2 z-40 h-[4px] w-[4px] translate-x-[1.5px] translate-y-[14px] rounded-full bg-blue-600 blur-[3px]" />
					<motion.div className="absolute right-1/2 bottom-1/2 z-40 h-[2px] w-[2px] translate-x-[0.5px] translate-y-[14px] rounded-full bg-blue-300" />
				</>
			</div>
		</motion.div>
	);
};

export const FeatureIconContainer = ({
	children,
	className,
}: {
	children: React.ReactNode;
	className?: string;
}) => {
	return (
		<div
			className={cn(
				"relative h-14 w-14 rounded-md bg-gradient-to-b from-gray-50 to-neutral-200 p-[4px] dark:from-neutral-800 dark:to-neutral-950",
				className
			)}
		>
			<div
				className={cn(
					"relative z-20 h-full w-full rounded-[5px] bg-gray-50 dark:bg-neutral-800",
					className
				)}
			>
				{children}
			</div>
			<div className="absolute inset-x-0 bottom-0 z-30 mx-auto h-4 w-full rounded-full bg-neutral-600 opacity-50 blur-lg"></div>
			<div className="absolute inset-x-0 bottom-0 mx-auto h-px w-[60%] bg-gradient-to-r from-transparent via-blue-500 to-transparent"></div>
			<div className="absolute inset-x-0 bottom-0 mx-auto h-px w-[60%] bg-gradient-to-r from-transparent via-blue-600 to-transparent dark:h-[8px] dark:blur-sm"></div>
		</div>
	);
};

export const Grid = ({ pattern, size }: { pattern?: number[][]; size?: number }) => {
	const p = pattern ?? [
		[9, 3],
		[8, 5],
		[10, 2],
		[7, 4],
		[9, 6],
	];
	return (
		<div className="pointer-events-none absolute top-0 left-1/2 -mt-2 -ml-20 h-full w-full [mask-image:linear-gradient(white,transparent)]">
			<div className="absolute inset-0 bg-gradient-to-r from-zinc-900/30 to-zinc-900/30 opacity-10 [mask-image:radial-gradient(farthest-side_at_top,white,transparent)] dark:from-zinc-900/30 dark:to-zinc-900/30">
				<GridPattern
					width={size ?? 20}
					height={size ?? 20}
					x="-12"
					y="4"
					squares={p}
					className="absolute inset-0 h-full w-full fill-black/100 stroke-black/100 mix-blend-overlay dark:fill-white/100 dark:stroke-white/100"
				/>
			</div>
		</div>
	);
};

export function GridPattern({ width, height, x, y, squares, ...props }: any) {
	const patternId = useId();

	return (
		<svg aria-hidden="true" {...props}>
			<defs>
				<pattern
					id={patternId}
					width={width}
					height={height}
					patternUnits="userSpaceOnUse"
					x={x}
					y={y}
				>
					<path d={`M.5 ${height}V.5H${width}`} fill="none" />
				</pattern>
			</defs>
			<rect width="100%" height="100%" strokeWidth={0} fill={`url(#${patternId})`} />
			{squares && (
				<svg aria-hidden="true" x={x} y={y} className="overflow-visible">
					{squares.map(([x, y]: any, idx: number) => (
						<rect
							strokeWidth="0"
							key={`${x}-${y}-${idx}`}
							width={width + 1}
							height={height + 1}
							x={x * width}
							y={y * height}
						/>
					))}
				</svg>
			)}
		</svg>
	);
}
