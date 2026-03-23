import type { Schema } from "@/zero/schema";

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
