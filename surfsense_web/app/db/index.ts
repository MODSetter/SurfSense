import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

// Configure postgres client for Vercel serverless environment
const client = postgres(process.env.DATABASE_URL!, {
	max: 1, // Limit connections for serverless (Vercel)
	idle_timeout: 20, // Close idle connections after 20 seconds
	max_lifetime: 60 * 30, // Close connections after 30 minutes
	connect_timeout: 10, // Connection timeout in seconds
});

export const db = drizzle({ client, schema });
