/**
 * DirectAI Database Schema — Drizzle ORM
 *
 * 6 tables:
 *   NextAuth-managed: users, accounts, sessions, verification_tokens
 *   DirectAI-managed: api_keys, usage_records
 *
 * All timestamps are UTC. IDs are UUIDs unless otherwise noted.
 * Compatible with @auth/drizzle-adapter for NextAuth v5.
 */

import {
  pgTable,
  text,
  timestamp,
  uuid,
  varchar,
  integer,
  bigint,
  primaryKey,
  index,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import type { AdapterAccountType } from "next-auth/adapters";

// ---------------------------------------------------------------------------
// NextAuth tables (schema matches @auth/drizzle-adapter expectations)
// ---------------------------------------------------------------------------

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name"),
  email: text("email").unique().notNull(),
  emailVerified: timestamp("email_verified", { mode: "date" }),
  image: text("image"),
  // DirectAI extensions — nullable, populated after Stripe sync
  stripeCustomerId: varchar("stripe_customer_id", { length: 255 }),
  tier: varchar("tier", { length: 20 }).default("developer").notNull(),
  createdAt: timestamp("created_at", { mode: "date" }).defaultNow().notNull(),
  updatedAt: timestamp("updated_at", { mode: "date" }).defaultNow().notNull(),
});

export const accounts = pgTable(
  "accounts",
  {
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    type: text("type").$type<AdapterAccountType>().notNull(),
    provider: text("provider").notNull(),
    providerAccountId: text("provider_account_id").notNull(),
    refresh_token: text("refresh_token"),
    access_token: text("access_token"),
    expires_at: integer("expires_at"),
    token_type: text("token_type"),
    scope: text("scope"),
    id_token: text("id_token"),
    session_state: text("session_state"),
  },
  (account) => [
    primaryKey({
      columns: [account.provider, account.providerAccountId],
    }),
  ]
);

export const sessions = pgTable("sessions", {
  sessionToken: text("session_token").primaryKey(),
  userId: uuid("user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  expires: timestamp("expires", { mode: "date" }).notNull(),
});

export const verificationTokens = pgTable(
  "verification_tokens",
  {
    identifier: text("identifier").notNull(),
    token: text("token").notNull(),
    expires: timestamp("expires", { mode: "date" }).notNull(),
  },
  (vt) => [
    primaryKey({ columns: [vt.identifier, vt.token] }),
  ]
);

// ---------------------------------------------------------------------------
// DirectAI tables
// ---------------------------------------------------------------------------

export const apiKeys = pgTable(
  "api_keys",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    /** SHA-256 hash of the full API key. Never store plaintext. */
    keyHash: varchar("key_hash", { length: 64 }).notNull().unique(),
    /** First 8 chars of the key for display (e.g., "dai_sk_a1b2..."). */
    keyPrefix: varchar("key_prefix", { length: 16 }).notNull(),
    /** User-assigned name for the key (e.g., "production", "staging"). */
    name: varchar("name", { length: 255 }).notNull(),
    createdAt: timestamp("created_at", { mode: "date" }).defaultNow().notNull(),
    lastUsedAt: timestamp("last_used_at", { mode: "date" }),
    revokedAt: timestamp("revoked_at", { mode: "date" }),
  },
  (key) => [
    index("idx_api_keys_user_id").on(key.userId),
    uniqueIndex("idx_api_keys_key_hash").on(key.keyHash),
  ]
);

export const usageRecords = pgTable(
  "usage_records",
  {
    id: bigint("id", { mode: "bigint" }).primaryKey().generatedAlwaysAsIdentity(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    apiKeyId: uuid("api_key_id").references(() => apiKeys.id, {
      onDelete: "set null",
    }),
    /** Model name as sent in the API request (e.g., "llama-3.1-70b-instruct"). */
    model: varchar("model", { length: 255 }).notNull(),
    /** Modality: chat, embedding, transcription. */
    modality: varchar("modality", { length: 20 }).notNull(),
    /** Input tokens (prompt). 0 for transcription. */
    inputTokens: integer("input_tokens").default(0).notNull(),
    /** Output tokens (completion). 0 for embeddings. */
    outputTokens: integer("output_tokens").default(0).notNull(),
    /** Correlation ID from the API request (X-Request-ID). */
    requestId: uuid("request_id"),
    createdAt: timestamp("created_at", { mode: "date" }).defaultNow().notNull(),
  },
  (record) => [
    index("idx_usage_records_user_id").on(record.userId),
    index("idx_usage_records_created_at").on(record.createdAt),
    index("idx_usage_records_user_model").on(record.userId, record.model),
  ]
);
