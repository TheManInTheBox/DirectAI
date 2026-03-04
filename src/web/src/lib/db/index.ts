/**
 * Database connection — Drizzle ORM + postgres.js
 *
 * Uses the `postgres` driver (by @porsager) for connection pooling.
 * Connection string from DATABASE_URL env var.
 *
 * Usage:
 *   import { db } from "@/lib/db";
 *   const users = await db.select().from(schema.users);
 */

import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

function createDb() {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      "DATABASE_URL is not set. Expected format: postgresql://user:password@host:5432/directai?sslmode=require"
    );
  }

  const client = postgres(connectionString, {
    max: process.env.NODE_ENV === "production" ? 25 : 5,
    idle_timeout: 20,
    connect_timeout: 10,
    ssl: process.env.NODE_ENV === "production" ? "require" : false,
  });

  return drizzle(client, { schema });
}

// Lazy singleton — only created when first accessed via getDb()
let _db: ReturnType<typeof createDb> | undefined;

/**
 * Get the database instance. Lazy — creates the connection on first call.
 * Throws if DATABASE_URL is not set.
 */
export function getDb() {
  if (!_db) {
    _db = createDb();
  }
  return _db;
}

/**
 * Direct db export for convenience in queries.
 * NOTE: At build time (next build), DATABASE_URL may not be set.
 * This will throw at runtime if DATABASE_URL is missing.
 */
export const db = process.env.DATABASE_URL ? createDb() : (undefined as unknown as ReturnType<typeof createDb>);

export type Database = ReturnType<typeof createDb>;
