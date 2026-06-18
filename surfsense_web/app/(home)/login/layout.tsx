import { RuntimeConfig } from "@/components/providers/runtime-config.server";

export default function LoginLayout({ children }: { children: React.ReactNode }) {
	return <RuntimeConfig>{children}</RuntimeConfig>;
}
