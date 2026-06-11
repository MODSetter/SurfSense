import { number, string, table } from "@rocicorp/zero";

/**
 * Live-meter slice of the ``user`` table replicated through Zero.
 *
 * ``creditMicrosBalance`` is stored as integer micro-USD (1_000_000 == $1.00);
 * UI consumers divide by 1M when displaying and clamp at $0.00 (the balance can
 * dip slightly negative when actual cost exceeds the pre-charge estimate).
 * Sensitive fields (email, hashed_password, oauth, etc.) are intentionally
 * omitted via the Postgres column-list publication so they never enter WAL
 * replication.
 */
export const userTable = table("user")
	.columns({
		id: string(),
		creditMicrosBalance: number().from("credit_micros_balance"),
	})
	.primaryKey("id");
