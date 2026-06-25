import type { Schema } from "@/zero/schema/index";

export type Context =
	| {
			userId: string;
			allowedSpaceIds?: number[];
	  }
	| undefined;

declare module "@rocicorp/zero" {
	interface DefaultTypes {
		context: Context;
		schema: Schema;
	}
}
