/**
 * Electric SQL client setup for ElectricSQL 1.x with PGlite
 *
 * USER-SPECIFIC DATABASE ARCHITECTURE:
 * - Each user gets their own IndexedDB database: idb://surfsense-{userId}-v{version}
 * - On login: cleanup databases from other users, then initialize current user's DB
 * - On logout: best-effort cleanup (not relied upon)
 *
 * This ensures:
 * 1. Complete user isolation (data can never leak between users)
 * 2. Self-healing on login (stale databases are cleaned up)
 * 3. Works even if logout cleanup fails
 */

import { PGlite, type Transaction } from "@electric-sql/pglite";
import { live } from "@electric-sql/pglite/live";
import { electricSync } from "@electric-sql/pglite-sync";

// Debug logging - only logs in development, silent in production
const IS_DEV = process.env.NODE_ENV === "development";

function debugLog(...args: unknown[]) {
	if (IS_DEV) console.log(...args);
}

function debugWarn(...args: unknown[]) {
	if (IS_DEV) console.warn(...args);
}

// Types
export interface ElectricClient {
	db: PGlite;
	userId: string;
	syncShape: (options: SyncShapeOptions) => Promise<SyncHandle>;
}

export interface SyncShapeOptions {
	table: string;
	where?: string;
	columns?: string[];
	primaryKey?: string[];
}

export interface SyncHandle {
	unsubscribe: () => void;
	readonly isUpToDate: boolean;
	// The stream property contains the ShapeStreamInterface from pglite-sync
	stream?: unknown;
	// Promise that resolves when initial sync is complete
	initialSyncPromise?: Promise<void>;
}

// Singleton state - now tracks the user ID
let electricClient: ElectricClient | null = null;
let currentUserId: string | null = null;
let isInitializing = false;
let initPromise: Promise<ElectricClient> | null = null;

// Cache for sync handles to prevent duplicate subscriptions (memory optimization)
const activeSyncHandles = new Map<string, SyncHandle>();

// Track pending sync operations to prevent race conditions
// If a sync is in progress, subsequent calls will wait for it instead of starting a new one
const pendingSyncs = new Map<string, Promise<SyncHandle>>();

// Version for sync state - increment this to force fresh sync when Electric config changes
// v2: user-specific database architecture
// v3: consistent cutoff date for sync+queries, visibility refresh support
// v4: heartbeat-based stale notification detection with updated_at tracking
// v5: fixed duplicate key errors, stable cutoff dates, onMustRefetch handler,
//     real-time documents table with title/created_by_id/status columns,
//     consolidated single documents sync, pending state for document queue visibility
// v6: added enable_summary column to search_source_connectors
const SYNC_VERSION = 6;

// Database name prefix for identifying SurfSense databases
const DB_PREFIX = "surfsense-";

// Get Electric URL from environment
function getElectricUrl(): string {
	if (typeof window !== "undefined") {
		return process.env.NEXT_PUBLIC_ELECTRIC_URL || "http://localhost:5133";
	}
	return "http://localhost:5133";
}

/**
 * Get the database name for a specific user
 */
function getDbName(userId: string): string {
	return `idb://${DB_PREFIX}${userId}-v${SYNC_VERSION}`;
}

/**
 * Clean up databases from OTHER users AND old versions
 * This is called on login to ensure clean state
 */
async function cleanupOtherUserDatabases(currentUserId: string): Promise<void> {
	if (typeof window === "undefined" || !window.indexedDB) {
		return;
	}

	// The exact database identifier we want to keep (current user + current version)
	// Format: "surfsense-{userId}-v{version}"
	const currentDbIdentifier = `${DB_PREFIX}${currentUserId}-v${SYNC_VERSION}`;

	try {
		// Try to list all databases (not supported in all browsers)
		if (typeof window.indexedDB.databases === "function") {
			const databases = await window.indexedDB.databases();

			for (const dbInfo of databases) {
				const dbName = dbInfo.name;
				if (!dbName) continue;

				// Check if this is a SurfSense database
				if (dbName.includes("surfsense")) {
					// Check if this is the current database
					// PGlite stores with "/pglite/" prefix, so we check if the name ENDS WITH our identifier
					if (dbName.endsWith(currentDbIdentifier)) {
						debugLog(`[Electric] Keeping current database: ${dbName}`);
						continue;
					}

					// Delete ALL other databases (other users OR old versions of current user)
					try {
						debugLog(`[Electric] Deleting stale database: ${dbName}`);
						window.indexedDB.deleteDatabase(dbName);
					} catch (deleteErr) {
						debugWarn(`[Electric] Failed to delete database ${dbName}:`, deleteErr);
					}
				}
			}
		}
	} catch (err) {
		// indexedDB.databases() not supported - that's okay, login cleanup is best-effort
		debugWarn("[Electric] Could not enumerate databases for cleanup:", err);
	}
}

/**
 * Initialize the Electric SQL client for a specific user
 *
 * KEY BEHAVIORS:
 * 1. If already initialized for the SAME user, returns existing client
 * 2. If initialized for a DIFFERENT user, closes old client and creates new one
 * 3. On first init, cleans up databases from other users
 *
 * @param userId - The current user's ID (required)
 */
export async function initElectric(userId: string): Promise<ElectricClient> {
	if (!userId) {
		throw new Error("userId is required for Electric initialization");
	}

	// If already initialized for this user, return existing client
	if (electricClient && currentUserId === userId) {
		return electricClient;
	}

	// If initialized for a different user, close the old client first
	if (electricClient && currentUserId !== userId) {
		debugLog(`[Electric] User changed from ${currentUserId} to ${userId}, reinitializing...`);
		await cleanupElectric();
	}

	// If already initializing, wait for it
	if (isInitializing && initPromise) {
		return initPromise;
	}

	isInitializing = true;
	currentUserId = userId;

	initPromise = (async () => {
		try {
			// STEP 1: Clean up databases from other users (login-time cleanup)
			debugLog("[Electric] Cleaning up databases from other users...");
			await cleanupOtherUserDatabases(userId);

			// STEP 2: Create user-specific PGlite database
			const dbName = getDbName(userId);
			debugLog(`[Electric] Initializing database: ${dbName}`);

			const db = await PGlite.create({
				dataDir: dbName,
				relaxedDurability: true,
				extensions: {
					// Enable debug mode in electricSync only in development
					electric: electricSync({ debug: process.env.NODE_ENV === "development" }),
					live, // Enable live queries for real-time updates
				},
			});

			// STEP 3: Create the notifications table schema in PGlite
			// This matches the backend schema
			await db.exec(`
				CREATE TABLE IF NOT EXISTS notifications (
					id INTEGER PRIMARY KEY,
					user_id TEXT NOT NULL,
					search_space_id INTEGER,
					type TEXT NOT NULL,
					title TEXT NOT NULL,
					message TEXT NOT NULL,
					read BOOLEAN NOT NULL DEFAULT FALSE,
					metadata JSONB DEFAULT '{}',
					created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
					updated_at TIMESTAMPTZ
				);
				
				CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
				CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);
			`);

			// Create the search_source_connectors table schema in PGlite
			// This matches the backend schema
			await db.exec(`
			CREATE TABLE IF NOT EXISTS search_source_connectors (
				id INTEGER PRIMARY KEY,
				search_space_id INTEGER NOT NULL,
				user_id TEXT NOT NULL,
				connector_type TEXT NOT NULL,
				name TEXT NOT NULL,
				is_indexable BOOLEAN NOT NULL DEFAULT FALSE,
				last_indexed_at TIMESTAMPTZ,
				config JSONB DEFAULT '{}',
				periodic_indexing_enabled BOOLEAN NOT NULL DEFAULT FALSE,
				indexing_frequency_minutes INTEGER,
				next_scheduled_at TIMESTAMPTZ,
				enable_summary BOOLEAN NOT NULL DEFAULT FALSE,
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
			);
				
				CREATE INDEX IF NOT EXISTS idx_connectors_search_space_id ON search_source_connectors(search_space_id);
				CREATE INDEX IF NOT EXISTS idx_connectors_type ON search_source_connectors(connector_type);
				CREATE INDEX IF NOT EXISTS idx_connectors_user_id ON search_source_connectors(user_id);
			`);

			// Create the documents table schema in PGlite
			// Sync columns needed for real-time table display (lightweight - no content/metadata)
			await db.exec(`
				CREATE TABLE IF NOT EXISTS documents (
					id INTEGER PRIMARY KEY,
					search_space_id INTEGER NOT NULL,
					document_type TEXT NOT NULL,
					title TEXT NOT NULL DEFAULT '',
					created_by_id TEXT,
					created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
					status JSONB DEFAULT '{"state": "ready"}'::jsonb
				);
				
				CREATE INDEX IF NOT EXISTS idx_documents_search_space_id ON documents(search_space_id);
				CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
				CREATE INDEX IF NOT EXISTS idx_documents_search_space_type ON documents(search_space_id, document_type);
				CREATE INDEX IF NOT EXISTS idx_documents_status ON documents((status->>'state'));
			`);

			await db.exec(`
				CREATE TABLE IF NOT EXISTS chat_comment_mentions (
					id INTEGER PRIMARY KEY,
					comment_id INTEGER NOT NULL,
					mentioned_user_id TEXT NOT NULL,
					created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
				);
				
				CREATE INDEX IF NOT EXISTS idx_chat_comment_mentions_user_id ON chat_comment_mentions(mentioned_user_id);
				CREATE INDEX IF NOT EXISTS idx_chat_comment_mentions_comment_id ON chat_comment_mentions(comment_id);
			`);

			// Create chat_comments table for live comment sync
			await db.exec(`
				CREATE TABLE IF NOT EXISTS chat_comments (
					id INTEGER PRIMARY KEY,
					message_id INTEGER NOT NULL,
					thread_id INTEGER NOT NULL,
					parent_id INTEGER,
					author_id TEXT,
					content TEXT NOT NULL,
					created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
					updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
				);
				
				CREATE INDEX IF NOT EXISTS idx_chat_comments_thread_id ON chat_comments(thread_id);
				CREATE INDEX IF NOT EXISTS idx_chat_comments_message_id ON chat_comments(message_id);
				CREATE INDEX IF NOT EXISTS idx_chat_comments_parent_id ON chat_comments(parent_id);
			`);

			// Create new_chat_messages table for live message sync
			await db.exec(`
				CREATE TABLE IF NOT EXISTS new_chat_messages (
					id INTEGER PRIMARY KEY,
					thread_id INTEGER NOT NULL,
					role TEXT NOT NULL,
					content JSONB NOT NULL,
					author_id TEXT,
					created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
				);
				
				CREATE INDEX IF NOT EXISTS idx_new_chat_messages_thread_id ON new_chat_messages(thread_id);
				CREATE INDEX IF NOT EXISTS idx_new_chat_messages_created_at ON new_chat_messages(created_at);
			`);

			const electricUrl = getElectricUrl();

			// STEP 4: Create the client wrapper
			electricClient = {
				db,
				userId,
				syncShape: async (options: SyncShapeOptions): Promise<SyncHandle> => {
					const { table, where, columns, primaryKey = ["id"] } = options;

					// Create cache key for this sync shape
					const cacheKey = `${table}_${where || "all"}_${columns?.join(",") || "all"}`;

					// Check if we already have an active sync for this shape (memory optimization)
					const existingHandle = activeSyncHandles.get(cacheKey);
					if (existingHandle) {
						debugLog(`[Electric] Reusing existing sync handle for: ${cacheKey}`);
						return existingHandle;
					}

					// Check if there's already a pending sync for this shape (prevent race condition)
					const pendingSync = pendingSyncs.get(cacheKey);
					if (pendingSync) {
						debugLog(`[Electric] Waiting for pending sync to complete: ${cacheKey}`);
						return pendingSync;
					}

					// Create and track the sync promise to prevent race conditions
					const syncPromise = (async (): Promise<SyncHandle> => {
						// Build params for the shape request
						// Electric SQL expects params as URL query parameters
						const params: Record<string, string> = { table };

						// Validate and fix WHERE clause to ensure string literals are properly quoted
						let validatedWhere = where;
						if (where) {
							// Check if where uses positional parameters
							if (where.includes("$1")) {
								// Extract the value from the where clause if it's embedded
								// For now, we'll use the where clause as-is and let Electric handle it
								params.where = where;
								validatedWhere = where;
							} else {
								// Validate that string literals are properly quoted
								// Count single quotes - should be even (pairs) for properly quoted strings
								const singleQuoteCount = (where.match(/'/g) || []).length;

								if (singleQuoteCount % 2 !== 0) {
									// Odd number of quotes means unterminated string literal
									debugWarn("Where clause has unmatched quotes, fixing:", where);
									// Add closing quote at the end
									validatedWhere = `${where}'`;
									params.where = validatedWhere;
								} else {
									// Use the where clause directly (already formatted)
									params.where = where;
									validatedWhere = where;
								}
							}
						}

						if (columns) params.columns = columns.join(",");

						debugLog("[Electric] Syncing shape with params:", params);
						debugLog("[Electric] Electric URL:", `${electricUrl}/v1/shape`);
						debugLog("[Electric] Where clause:", where, "Validated:", validatedWhere);

						try {
							// Debug: Test Electric SQL connection directly first (DEV ONLY - skipped in production)
							if (process.env.NODE_ENV === "development") {
								const testUrl = `${electricUrl}/v1/shape?table=${table}&offset=-1${validatedWhere ? `&where=${encodeURIComponent(validatedWhere)}` : ""}`;
								debugLog("[Electric] Testing Electric SQL directly:", testUrl);
								try {
									const testResponse = await fetch(testUrl);
									const testHeaders = {
										handle: testResponse.headers.get("electric-handle"),
										offset: testResponse.headers.get("electric-offset"),
										upToDate: testResponse.headers.get("electric-up-to-date"),
									};
									debugLog("[Electric] Direct Electric SQL response headers:", testHeaders);
									const testData = await testResponse.json();
									debugLog(
										"[Electric] Direct Electric SQL data count:",
										Array.isArray(testData) ? testData.length : "not array",
										testData
									);
								} catch (testErr) {
									console.error("[Electric] Direct Electric SQL test failed:", testErr);
								}
							}

							// Use PGlite's electric sync plugin to sync the shape
							// According to Electric SQL docs, the shape config uses params for table, where, columns
							// Note: mapColumns is OPTIONAL per pglite-sync types.ts

							// Create a promise that resolves when initial sync is complete
							// Using recommended approach: check isUpToDate immediately, watch stream, shorter timeout
							// IMPORTANT: We don't unsubscribe from the stream - it must stay active for real-time updates
							let syncResolved = false;
							// Initialize with no-op functions to satisfy TypeScript
							let resolveInitialSync: () => void = () => {};
							let rejectInitialSync: (error: Error) => void = () => {};

							const initialSyncPromise = new Promise<void>((resolve, reject) => {
								resolveInitialSync = () => {
									if (!syncResolved) {
										syncResolved = true;
										// DON'T unsubscribe from stream - it needs to stay active for real-time updates
										resolve();
									}
								};
								rejectInitialSync = (error: Error) => {
									if (!syncResolved) {
										syncResolved = true;
										// DON'T unsubscribe from stream even on error - let Electric handle it
										reject(error);
									}
								};

								// Shorter timeout (5 seconds) as fallback
								setTimeout(() => {
									if (!syncResolved) {
										debugWarn(
											`[Electric] ⚠️ Sync timeout for ${table} - checking isUpToDate one more time...`
										);
										// Check isUpToDate one more time before resolving
										// This will be checked after shape is created
										setTimeout(() => {
											if (!syncResolved) {
												debugWarn(
													`[Electric] ⚠️ Sync timeout for ${table} - resolving anyway after 5s`
												);
												resolveInitialSync();
											}
										}, 100);
									}
								}, 5000);
							});

							// ROOT CAUSE FIX: The duplicate key errors were caused by unstable cutoff dates
							// in use-inbox.ts generating different sync keys on each render.
							// That's now fixed (rounded to midnight UTC in getSyncCutoffDate).
							// We can safely use shapeKey for fast incremental sync.

							const shapeKey = `${userId}_v${SYNC_VERSION}_${table}_${where?.replace(/[^a-zA-Z0-9]/g, "_") || "all"}`;

							// Type assertion to PGlite with electric extension
							const pgWithElectric = db as unknown as {
								electric: {
									syncShapeToTable: (
										config: Record<string, unknown>
									) => Promise<{ unsubscribe: () => void; isUpToDate: boolean; stream: unknown }>;
								};
							};

							const shapeConfig = {
								shape: {
									url: `${electricUrl}/v1/shape`,
									params: {
										table,
										...(validatedWhere ? { where: validatedWhere } : {}),
										...(columns ? { columns: columns.join(",") } : {}),
									},
								},
								table,
								primaryKey,
								shapeKey, // Re-enabled for fast incremental sync (root cause in use-inbox.ts is fixed)
								onInitialSync: () => {
									debugLog(
										`[Electric] ✅ Initial sync complete for ${table} - data should now be in PGlite`
									);
									resolveInitialSync();
								},
								onError: (error: Error) => {
									console.error(`[Electric] ❌ Shape sync error for ${table}:`, error);
									console.error(
										"[Electric] Error details:",
										JSON.stringify(error, Object.getOwnPropertyNames(error))
									);
									rejectInitialSync(error);
								},
								// Handle must-refetch: clear table data before Electric re-inserts from scratch
								// This prevents "duplicate key" errors when the shape is invalidated
								onMustRefetch: async (tx: Transaction) => {
									debugLog(
										`[Electric] ⚠️ Must refetch triggered for ${table} - clearing existing data`
									);
									try {
										// Delete rows matching the shape's WHERE clause
										// If no WHERE clause, delete all rows from the table
										if (validatedWhere) {
											// Parse the WHERE clause to build a DELETE statement
											// The WHERE clause is already validated and formatted
											await tx.exec(`DELETE FROM ${table} WHERE ${validatedWhere}`);
											debugLog(`[Electric] 🗑️ Cleared ${table} rows matching: ${validatedWhere}`);
										} else {
											// No WHERE clause means we're syncing the entire table
											await tx.exec(`DELETE FROM ${table}`);
											debugLog(`[Electric] 🗑️ Cleared all rows from ${table}`);
										}
									} catch (cleanupError) {
										console.error(
											`[Electric] ❌ Failed to clear ${table} during must-refetch:`,
											cleanupError
										);
										// Re-throw to let Electric handle the error
										throw cleanupError;
									}
								},
							};

							debugLog("[Electric] syncShapeToTable config:", JSON.stringify(shapeConfig, null, 2));

							let shape: { unsubscribe: () => void; isUpToDate: boolean; stream: unknown };
							try {
								shape = await pgWithElectric.electric.syncShapeToTable(shapeConfig);
							} catch (syncError) {
								// Handle "Already syncing" error - pglite-sync might not have fully cleaned up yet
								const errorMessage =
									syncError instanceof Error ? syncError.message : String(syncError);
								if (errorMessage.includes("Already syncing")) {
									debugWarn(
										`[Electric] Already syncing ${table}, waiting for existing sync to settle...`
									);

									// Wait a short time for pglite-sync to settle
									await new Promise((resolve) => setTimeout(resolve, 100));

									// Check if an active handle now exists (another sync might have completed)
									const existingHandle = activeSyncHandles.get(cacheKey);
									if (existingHandle) {
										debugLog(`[Electric] Found existing handle after waiting: ${cacheKey}`);
										return existingHandle;
									}

									// Retry once after waiting
									debugLog(`[Electric] Retrying sync for ${table}...`);
									try {
										shape = await pgWithElectric.electric.syncShapeToTable(shapeConfig);
									} catch (retryError) {
										const retryMessage =
											retryError instanceof Error ? retryError.message : String(retryError);
										if (retryMessage.includes("Already syncing")) {
											// Still syncing - create a placeholder handle that indicates the table is being synced
											debugWarn(`[Electric] ${table} still syncing, creating placeholder handle`);
											const placeholderHandle: SyncHandle = {
												unsubscribe: () => {
													debugLog(`[Electric] Placeholder unsubscribe for: ${cacheKey}`);
													activeSyncHandles.delete(cacheKey);
												},
												get isUpToDate() {
													return false; // We don't know the real state
												},
												stream: undefined,
												initialSyncPromise: Promise.resolve(), // Already syncing means data should be coming
											};
											activeSyncHandles.set(cacheKey, placeholderHandle);
											return placeholderHandle;
										}
										throw retryError;
									}
								} else {
									throw syncError;
								}
							}

							if (!shape) {
								throw new Error("syncShapeToTable returned undefined");
							}

							// Log the actual shape result structure
							debugLog("[Electric] Shape sync result (initial):", {
								hasUnsubscribe: typeof shape?.unsubscribe === "function",
								isUpToDate: shape?.isUpToDate,
								hasStream: !!shape?.stream,
								streamType: typeof shape?.stream,
							});

							// Recommended Approach Step 1: Check isUpToDate immediately
							if (shape.isUpToDate) {
								debugLog(
									`[Electric] ✅ Sync already up-to-date for ${table} (resuming from previous state)`
								);
								resolveInitialSync();
							} else {
								// Recommended Approach Step 2: Subscribe to stream and watch for "up-to-date" message
								if (shape?.stream) {
									const stream = shape.stream as any;
									debugLog("[Electric] Shape stream details:", {
										shapeHandle: stream?.shapeHandle,
										lastOffset: stream?.lastOffset,
										isUpToDate: stream?.isUpToDate,
										error: stream?.error,
										hasSubscribe: typeof stream?.subscribe === "function",
										hasUnsubscribe: typeof stream?.unsubscribe === "function",
									});

									// Subscribe to the stream to watch for "up-to-date" control message
									// NOTE: We keep this subscription active - don't unsubscribe!
									// The stream is what Electric SQL uses for real-time updates
									if (typeof stream?.subscribe === "function") {
										debugLog(
											"[Electric] Subscribing to shape stream to watch for up-to-date message..."
										);
										// Subscribe but don't store unsubscribe - we want it to stay active
										stream.subscribe((messages: unknown[]) => {
											// Continue receiving updates even after sync is resolved
											if (!syncResolved) {
												debugLog(
													"[Electric] 🔵 Shape stream received messages:",
													messages?.length || 0
												);
											}

											// Check if any message indicates sync is complete
											if (messages && messages.length > 0) {
												for (const message of messages) {
													const msg = message as any;
													// Check for "up-to-date" control message
													if (
														msg?.headers?.control === "up-to-date" ||
														msg?.headers?.electric_up_to_date === "true" ||
														(typeof msg === "object" && "up-to-date" in msg)
													) {
														if (!syncResolved) {
															debugLog(`[Electric] ✅ Received up-to-date message for ${table}`);
															resolveInitialSync();
														}
														// Continue listening for real-time updates - don't return!
													}
												}
												if (!syncResolved && messages.length > 0) {
													debugLog(
														"[Electric] First message:",
														JSON.stringify(messages[0], null, 2)
													);
												}
											}

											// Also check stream's isUpToDate property after receiving messages
											if (!syncResolved && stream?.isUpToDate) {
												debugLog(`[Electric] ✅ Stream isUpToDate is true for ${table}`);
												resolveInitialSync();
											}
										});

										// Also check stream's isUpToDate property immediately
										if (stream?.isUpToDate) {
											debugLog(`[Electric] ✅ Stream isUpToDate is true immediately for ${table}`);
											resolveInitialSync();
										}
									}

									// Also poll isUpToDate periodically as a backup (every 200ms)
									const pollInterval = setInterval(() => {
										if (syncResolved) {
											clearInterval(pollInterval);
											return;
										}

										if (shape.isUpToDate || stream?.isUpToDate) {
											debugLog(`[Electric] ✅ Sync completed (detected via polling) for ${table}`);
											clearInterval(pollInterval);
											resolveInitialSync();
										}
									}, 200);

									// Clean up polling when promise resolves
									initialSyncPromise.finally(() => {
										clearInterval(pollInterval);
									});
								} else {
									debugWarn(
										`[Electric] ⚠️ No stream available for ${table}, relying on callback and timeout`
									);
								}
							}

							// Create the sync handle with proper cleanup
							const syncHandle: SyncHandle = {
								unsubscribe: () => {
									debugLog(`[Electric] Unsubscribing from: ${cacheKey}`);
									// Remove from cache first
									activeSyncHandles.delete(cacheKey);
									// Then unsubscribe from the shape
									if (shape && typeof shape.unsubscribe === "function") {
										shape.unsubscribe();
									}
								},
								// Use getter to always return current state
								get isUpToDate() {
									return shape?.isUpToDate ?? false;
								},
								stream: shape?.stream,
								initialSyncPromise, // Expose promise so callers can wait for sync
							};

							// Cache the sync handle for reuse (memory optimization)
							activeSyncHandles.set(cacheKey, syncHandle);
							debugLog(
								`[Electric] Cached sync handle for: ${cacheKey} (total cached: ${activeSyncHandles.size})`
							);

							return syncHandle;
						} catch (error) {
							console.error("[Electric] Failed to sync shape:", error);
							// Check if Electric SQL server is reachable
							try {
								const response = await fetch(`${electricUrl}/v1/shape?table=${table}&offset=-1`, {
									method: "GET",
								});
								debugLog(
									"[Electric] Electric SQL server response:",
									response.status,
									response.statusText
								);
								if (!response.ok) {
									console.error("[Electric] Electric SQL server error:", await response.text());
								}
							} catch (fetchError) {
								console.error("[Electric] Cannot reach Electric SQL server:", fetchError);
								console.error("[Electric] Make sure Electric SQL is running at:", electricUrl);
							}
							throw error;
						}
					})();

					// Track the sync promise to prevent concurrent syncs for the same shape
					pendingSyncs.set(cacheKey, syncPromise);

					// Clean up the pending sync when done (whether success or failure)
					syncPromise.finally(() => {
						pendingSyncs.delete(cacheKey);
						debugLog(`[Electric] Pending sync removed for: ${cacheKey}`);
					});

					return syncPromise;
				},
			};

			debugLog(`[Electric] ✅ Initialized successfully for user: ${userId}`);
			return electricClient;
		} catch (error) {
			console.error("[Electric] Failed to initialize:", error);
			// Reset state on failure
			electricClient = null;
			currentUserId = null;
			throw error;
		} finally {
			isInitializing = false;
		}
	})();

	return initPromise;
}

/**
 * Cleanup Electric SQL - close database and reset singleton
 * Called on logout (best-effort) and when switching users
 */
export async function cleanupElectric(): Promise<void> {
	if (!electricClient) {
		return;
	}

	const userIdToClean = currentUserId;
	debugLog(`[Electric] Cleaning up for user: ${userIdToClean}`);

	// Unsubscribe from all active sync handles first (memory cleanup)
	debugLog(`[Electric] Unsubscribing from ${activeSyncHandles.size} active sync handles`);
	// Copy keys to array to avoid mutation during iteration
	const handleKeys = Array.from(activeSyncHandles.keys());
	for (const key of handleKeys) {
		const handle = activeSyncHandles.get(key);
		if (handle) {
			try {
				handle.unsubscribe();
			} catch (err) {
				debugWarn(`[Electric] Failed to unsubscribe from ${key}:`, err);
			}
		}
	}
	// Ensure caches are empty
	activeSyncHandles.clear();
	pendingSyncs.clear();

	try {
		// Close the PGlite database connection
		await electricClient.db.close();
		debugLog("[Electric] Database closed");
	} catch (error) {
		console.error("[Electric] Error closing database:", error);
	}

	// Reset singleton state
	electricClient = null;
	currentUserId = null;
	isInitializing = false;
	initPromise = null;

	// Delete the user's IndexedDB database (best-effort cleanup on logout)
	if (typeof window !== "undefined" && window.indexedDB && userIdToClean) {
		try {
			const dbName = `${DB_PREFIX}${userIdToClean}-v${SYNC_VERSION}`;
			window.indexedDB.deleteDatabase(dbName);
			debugLog(`[Electric] Deleted database: ${dbName}`);
		} catch (err) {
			debugWarn("[Electric] Failed to delete database:", err);
		}
	}

	debugLog("[Electric] Cleanup complete");
}

/**
 * Get the Electric client (throws if not initialized)
 */
export function getElectric(): ElectricClient {
	if (!electricClient) {
		throw new Error("Electric not initialized. Call initElectric(userId) first.");
	}
	return electricClient;
}

/**
 * Check if Electric is initialized for a specific user
 */
export function isElectricInitialized(userId?: string): boolean {
	if (!electricClient) return false;
	if (userId && currentUserId !== userId) return false;
	return true;
}

/**
 * Get the current user ID that Electric is initialized for
 */
export function getCurrentElectricUserId(): string | null {
	return currentUserId;
}

/**
 * Get the PGlite database instance
 */
export function getDb(): PGlite | null {
	return electricClient?.db ?? null;
}
