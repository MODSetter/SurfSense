import type { Schema } from "@/zero/schema/index";

export type Context =
	| {
			userId: string;
	  }
	| undefined;

declare module "@rocicorp/zero" {
	interface DefaultTypes {
		context: Context;
		schema: Schema;
	}
}
