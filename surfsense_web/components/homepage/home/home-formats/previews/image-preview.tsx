import Image from "next/image";
import footerScene from "@/components/site/site-footer-scene.webp";

/** A generated picture, shown with the site's own painted sky. */
export function ImagePreview() {
	return (
		<div className="w-full max-w-48 rotate-2 rounded-xl bg-card p-2 shadow-sm ring-1 ring-black/5">
			<Image
				src={footerScene}
				alt=""
				sizes="12rem"
				placeholder="blur"
				className="aspect-[4/3] w-full rounded-lg object-cover"
			/>
		</div>
	);
}
