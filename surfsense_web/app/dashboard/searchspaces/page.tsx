"use client";

import { useAtomValue } from "jotai";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { createSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { SearchSpaceForm } from "@/components/search-space-form";
import { trackSearchSpaceCreated } from "@/lib/posthog/events";

export default function SearchSpacesPage() {
	const router = useRouter();
	const { mutateAsync: createSearchSpace } = useAtomValue(createSearchSpaceMutationAtom);

	const handleCreateSearchSpace = async (data: { name: string; description?: string }) => {
		const result = await createSearchSpace({
			name: data.name,
			description: data.description || "",
		});

		// Track search space creation
		trackSearchSpaceCreated(result.id, data.name);

		// Redirect to the newly created search space's onboarding
		router.push(`/dashboard/${result.id}/onboard`);

		return result;
	};

	return (
		<motion.div
			className="mx-auto max-w-5xl px-4 py-6 lg:py-10"
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
