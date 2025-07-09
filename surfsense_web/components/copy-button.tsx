"use client";
import { useState } from "react";
import type { RefObject } from "react";
import { Button } from "./ui/button";
import { Copy, CopyCheck } from "lucide-react";

export default function CopyButton({
	ref,
}: {
	ref: RefObject<HTMLDivElement | null>;
}) {
	const [copy, setCopy] = useState(false);

	const handleClick = () => {
		if (ref.current) {
			const text = ref.current.innerText;
			navigator.clipboard.writeText(text);

			setCopy(true);
			setTimeout(() => {
				setCopy(false);
			}, 500);
		}
	};

	return (
		<div className="w-full flex justify-end">
			<Button variant="ghost" onClick={handleClick}>
				{copy ? <CopyCheck /> : <Copy />}
			</Button>
		</div>
	);
}
