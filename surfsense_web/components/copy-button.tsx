"use client";
import { Copy, CopyCheck } from "lucide-react";
import type { RefObject } from "react";
import { useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";

export default function CopyButton({ ref }: { ref: RefObject<HTMLDivElement | null> }) {
	const [copy, setCopy] = useState(false);
	const timeoutRef = useRef<NodeJS.Timeout | null>(null);

	useEffect(() => {
		return () => {
			if (timeoutRef.current) {
				clearTimeout(timeoutRef.current);
			}
		};
	}, []);

	const handleClick = () => {
		if (ref.current) {
			const text = ref.current.innerText;
			navigator.clipboard.writeText(text);

			setCopy(true);
			timeoutRef.current = setTimeout(() => {
				setCopy(false);
			}, 2000);
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
