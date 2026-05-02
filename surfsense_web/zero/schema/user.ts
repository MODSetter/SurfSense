import { number, string, table } from "@rocicorp/zero";

/**
 * Live-meter slice of the ``user`` table replicated through Zero.
 *
 * ``premiumCreditMicrosLimit`` / ``premiumCreditMicrosUsed`` are stored
 * as integer micro-USD (1_000_000 == $1.00). UI consumers divide by 1M
 * when displaying. Sensitive fields (email, hashed_password, oauth, etc.)
 * are intentionally omitted via the Postgres column-list publication so
 * they never enter WAL replication.
 */
export const userTable = table("user")
	.columns({
		id: string(),
		pagesLimit: number().from("pages_limit"),
		pagesUsed: number().from("pages_used"),
		premiumCreditMicrosLimit: number().from("premium_credit_micros_limit"),
		premiumCreditMicrosUsed: number().from("premium_credit_micros_used"),
	})
	.primaryKey("id");
