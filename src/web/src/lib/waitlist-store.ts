/**
 * Waitlist persistence layer.
 *
 * Uses PostgreSQL via Drizzle ORM (same DB as the rest of the app).
 * Falls back to in-memory Set only when DATABASE_URL is not set (local dev).
 */

import { createHash } from "crypto";

function hashEmail(email: string): string {
  return createHash("sha256").update(email).digest("hex");
}

// ── In-memory fallback (local dev only) ─────────────────────────────────

const memoryStore = new Set<string>();

// ── Public API ──────────────────────────────────────────────────────────

export async function addToWaitlist(email: string): Promise<{ alreadyExists: boolean }> {
  if (!process.env.DATABASE_URL) {
    if (memoryStore.has(email)) return { alreadyExists: true };
    memoryStore.add(email);
    console.log(`[waitlist] In-memory (no DATABASE_URL): ${email} (total: ${memoryStore.size})`);
    return { alreadyExists: false };
  }

  const { getDb } = await import("@/lib/db");
  const { waitlistEntries } = await import("@/lib/db/schema");
  const { eq } = await import("drizzle-orm");

  const db = getDb();
  const emailHash = hashEmail(email);

  // Check for duplicate
  const existing = await db
    .select({ id: waitlistEntries.id })
    .from(waitlistEntries)
    .where(eq(waitlistEntries.emailHash, emailHash))
    .limit(1);

  if (existing.length > 0) {
    return { alreadyExists: true };
  }

  await db.insert(waitlistEntries).values({
    email,
    emailHash,
    source: "website",
  });

  console.log(`[waitlist] Persisted to PostgreSQL: ${email}`);
  return { alreadyExists: false };
}
