/**
 * API Key Server Actions
 *
 * Generate, list, and revoke API keys. Keys are stored as SHA-256 hashes —
 * the plaintext is returned exactly once on creation and never persisted.
 */
"use server";

import { auth } from "@/lib/auth";
import { getDb } from "@/lib/db";
import { apiKeys } from "@/lib/db/schema";
import { eq, desc } from "drizzle-orm";
import { randomBytes, createHash } from "crypto";
import { revalidatePath } from "next/cache";

export async function createApiKey(name: string) {
  const session = await auth();
  if (!session?.user?.id) throw new Error("Unauthorized");

  const trimmed = name?.trim();
  if (!trimmed) throw new Error("Name is required");
  if (trimmed.length > 255) throw new Error("Name must be under 255 characters");

  // Generate key: dai_sk_ + 32 random bytes (64 hex chars)
  const raw = randomBytes(32).toString("hex");
  const key = `dai_sk_${raw}`;
  const hash = createHash("sha256").update(key).digest("hex");
  const prefix = key.substring(0, 15); // "dai_sk_" + first 8 hex

  const db = getDb();
  const [created] = await db
    .insert(apiKeys)
    .values({
      userId: session.user.id,
      keyHash: hash,
      keyPrefix: prefix,
      name: trimmed,
    })
    .returning({
      id: apiKeys.id,
      keyPrefix: apiKeys.keyPrefix,
      name: apiKeys.name,
      createdAt: apiKeys.createdAt,
    });

  revalidatePath("/dashboard/api-keys");

  // Return plaintext key — shown exactly once
  return { ...created, key };
}

export async function listApiKeys() {
  const session = await auth();
  if (!session?.user?.id) throw new Error("Unauthorized");

  const db = getDb();
  return db
    .select({
      id: apiKeys.id,
      keyPrefix: apiKeys.keyPrefix,
      name: apiKeys.name,
      createdAt: apiKeys.createdAt,
      lastUsedAt: apiKeys.lastUsedAt,
      revokedAt: apiKeys.revokedAt,
    })
    .from(apiKeys)
    .where(eq(apiKeys.userId, session.user.id))
    .orderBy(desc(apiKeys.createdAt));
}

export async function revokeApiKey(id: string) {
  const session = await auth();
  if (!session?.user?.id) throw new Error("Unauthorized");

  const db = getDb();
  const [key] = await db
    .select({ userId: apiKeys.userId })
    .from(apiKeys)
    .where(eq(apiKeys.id, id))
    .limit(1);

  if (!key || key.userId !== session.user.id) {
    throw new Error("Key not found");
  }

  await db
    .update(apiKeys)
    .set({ revokedAt: new Date() })
    .where(eq(apiKeys.id, id));

  revalidatePath("/dashboard/api-keys");
}
