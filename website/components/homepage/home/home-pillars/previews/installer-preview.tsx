import { type DockApp, MacOSDock } from "@/components/ui/mac-os-dock";

// The 21st.dev demo's icons, with SurfSense among them as the running app.
const APPS: DockApp[] = [
	{
		id: "finder",
		name: "Finder",
		icon: "https://cdn.21st.dev/assets/mirror/99/9963f31f43cd77b0c28981ba7bac04db749a5749019f554d1afb75225a3e9151.png",
	},
	{
		id: "notes",
		name: "Notes",
		icon: "https://cdn.21st.dev/assets/mirror/cb/cbfa4e5db383bbb86683edc2f7d309e9fd7000d07833f6449837be51b77558fa.png",
	},
	{ id: "surfsense", name: "SurfSense", icon: "/homepage/surfsense-dock-icon.svg" },
	{
		id: "mail",
		name: "Mail",
		icon: "https://cdn.21st.dev/assets/mirror/7b/7bb8671183d2a2bbb8a3858b1971cc5699ba0103673b011590d22f0fa309bb87.png",
	},
	{
		id: "safari",
		name: "Safari",
		icon: "https://cdn.21st.dev/assets/mirror/d5/d558230225bb0dd1897db6c7cf0d03b29506eef8078fe25313c48cd8f72d05ad.png",
	},
	{
		id: "calendar",
		name: "Calendar",
		icon: "https://cdn.21st.dev/assets/mirror/e1/e1e93987488d4a904f4b7273213d36319c73d81ca9680b440c144f69af5a7f9a.png",
	},
];

/** Installed like any app: SurfSense running in a desktop dock among the others. */
export function InstallerPreview() {
	return (
		<div aria-hidden="true" className="flex flex-col items-center">
			<MacOSDock
				apps={APPS}
				openApps={["surfsense"]}
				iconSize={36}
				maxScale={1.6}
				effectWidth={140}
				tone="light"
			/>
		</div>
	);
}
