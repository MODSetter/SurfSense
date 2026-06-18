import { RuntimeConfig } from "@/components/providers/runtime-config.server";
import { DashboardShell } from "./dashboard-shell";

interface DashboardLayoutProps {
	children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
	return (
		<RuntimeConfig>
			<DashboardShell>{children}</DashboardShell>
		</RuntimeConfig>
	);
}
