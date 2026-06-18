import { connection } from "next/server";
import { RuntimeConfigProvider } from "@/components/providers/runtime-config";
import {
	BUILD_TIME_AUTH_TYPE,
	BUILD_TIME_DEPLOYMENT_MODE,
	BUILD_TIME_ETL_SERVICE,
} from "@/lib/env-config";

export async function RuntimeConfig({ children }: { children: React.ReactNode }) {
	await connection();

	const value = {
		authType: process.env.AUTH_TYPE ?? BUILD_TIME_AUTH_TYPE,
		etlService: process.env.ETL_SERVICE ?? BUILD_TIME_ETL_SERVICE,
		deploymentMode: process.env.DEPLOYMENT_MODE ?? BUILD_TIME_DEPLOYMENT_MODE,
	};

	return <RuntimeConfigProvider value={value}>{children}</RuntimeConfigProvider>;
}
