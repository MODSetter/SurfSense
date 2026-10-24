import type { ReactNode } from "react";
import featuresScene from "@/components/homepage/home/home-features/features-scene.webp";
import { ScenePanel } from "@/components/homepage/home/home-features/scene-panel";
import { LaptopIcon, UserCircleIcon, WifiOffIcon } from "@/components/ui/icons";

// Network is the one row that is a setting, so it shows as a switch turned off.
function OffSwitch() {
	return (
		<span className="flex h-5 w-9 items-center rounded-full bg-white/25 p-0.5">
			<span className="size-4 rounded-full bg-white" />
		</span>
	);
}

function Row({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
	return (
		<div className="flex items-center gap-3 py-3 text-white [&_svg]:size-4">
			{icon}
			<span className="flex-1 text-sm">{label}</span>
			{typeof value === "string" ? <span className="text-sm text-white/80">{value}</span> : value}
		</div>
	);
}

/** The machine's state as a glass panel: offline, no account, data at home. */
export function PrivateVisual() {
	return (
		<ScenePanel scene={featuresScene} position="center 15%">
			<div className="mx-5 max-w-sm divide-y sm:mx-auto sm:w-full divide-white/20 rounded-3xl bg-black/20 px-5 py-2 backdrop-blur-sm">
				<Row icon={<WifiOffIcon />} label="Network" value={<OffSwitch />} />
				<Row icon={<UserCircleIcon />} label="Account" value="none" />
				<Row icon={<LaptopIcon />} label="Your data" value="Never uploaded" />
			</div>
		</ScenePanel>
	);
}
