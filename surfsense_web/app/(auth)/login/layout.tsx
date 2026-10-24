import { RuntimeConfig } from "@/components/providers/runtime-config.server";

export default function LoginLayout({ children }: { children: React.ReactNode }) {
	return (
		<RuntimeConfig>
			<main className="min-h-screen bg-main-panel text-foreground">{children}</main>
		</RuntimeConfig>
	);
}
