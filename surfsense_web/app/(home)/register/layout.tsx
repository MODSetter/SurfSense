import { RuntimeConfig } from "@/components/providers/runtime-config.server";

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
	return <RuntimeConfig>{children}</RuntimeConfig>;
}
