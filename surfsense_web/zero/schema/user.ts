import { number, string, table } from "@rocicorp/zero";

export const userTable = table("user")
	.columns({
		id: string(),
		pagesLimit: number().from("pages_limit"),
		pagesUsed: number().from("pages_used"),
		premiumTokensLimit: number().from("premium_tokens_limit"),
		premiumTokensUsed: number().from("premium_tokens_used"),
	})
	.primaryKey("id");
