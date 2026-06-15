import { connection } from "next/server";
import { RuntimeConfigProvider } from "@/components/providers/runtime-config";
import { AUTH_TYPE, DEPLOYMENT_MODE, ETL_SERVICE } from "@/lib/env-config";

export async function RuntimeConfig({ children }: { children: React.ReactNode }) {
	await connection();

	const value = {
		authType: process.env.AUTH_TYPE ?? AUTH_TYPE,
		etlService: process.env.ETL_SERVICE ?? ETL_SERVICE,
		deploymentMode: process.env.DEPLOYMENT_MODE ?? DEPLOYMENT_MODE,
	};

	return <RuntimeConfigProvider value={value}>{children}</RuntimeConfigProvider>;
}
