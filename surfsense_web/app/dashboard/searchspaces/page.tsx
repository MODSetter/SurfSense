"use client";

import { useAtomValue } from "jotai";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { SearchSpaceForm } from "@/components/search-space-form";
import { createSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";

export default function SearchSpacesPage() {
	const router = useRouter();
	const createSearchSpace = useAtomValue(createSearchSpaceMutationAtom);

	const handleCreateSearchSpace = async (data: { name: string; description?: string }) => {
		const result = await createSearchSpace.mutateAsync({
			name: data.name,
			description: data.description || "",
		});

		// Redirect to the newly created search space's onboarding
		router.push(`/dashboard/${result.id}/onboard`);

		return result;
	};

	return (
		<motion.div
			className="container mx-auto py-10"
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			transition={{ duration: 0.5 }}
		>
			<div className="mx-auto max-w-5xl">
				<SearchSpaceForm onSubmit={handleCreateSearchSpace} />
			</div>
		</motion.div>
	);
}
