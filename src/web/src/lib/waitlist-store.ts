/**
 * Waitlist persistence layer.
 *
 * Uses Azure Table Storage when AZURE_STORAGE_CONNECTION_STRING is set.
 * Falls back to in-memory Set for local dev / environments without Azure.
 *
 * Table schema:
 *   PartitionKey: "waitlist"
 *   RowKey: sha256(email) — deterministic, no PII in the key
 *   email: string
 *   signedUpAt: string (ISO 8601)
 *   source: "website"
 */

import { createHash } from "crypto";

const TABLE_NAME = "waitlist";
const PARTITION_KEY = "waitlist";

interface WaitlistEntry {
  email: string;
  signedUpAt: string;
  source: string;
}

// ── Azure Table Storage backend ──────────────────────────────────────────

let tableClient: import("@azure/data-tables").TableClient | null = null;

async function getTableClient() {
  if (tableClient) return tableClient;

  const connStr = process.env.AZURE_STORAGE_CONNECTION_STRING;
  if (!connStr) return null;

  const { TableClient, TableServiceClient } = await import("@azure/data-tables");

  // Ensure table exists (idempotent)
  const serviceClient = TableServiceClient.fromConnectionString(connStr);
  try {
    await serviceClient.createTable(TABLE_NAME);
  } catch (e: unknown) {
    // TableAlreadyExists is fine
    if (
      typeof e === "object" &&
      e !== null &&
      "statusCode" in e &&
      (e as { statusCode: number }).statusCode !== 409
    ) {
      throw e;
    }
  }

  tableClient = TableClient.fromConnectionString(connStr, TABLE_NAME);
  return tableClient;
}

function emailToRowKey(email: string): string {
  return createHash("sha256").update(email).digest("hex");
}

// ── In-memory fallback ──────────────────────────────────────────────────

const memoryStore = new Set<string>();

// ── Public API ──────────────────────────────────────────────────────────

export async function addToWaitlist(email: string): Promise<{ alreadyExists: boolean }> {
  const client = await getTableClient();

  if (client) {
    const rowKey = emailToRowKey(email);
    try {
      await client.getEntity(PARTITION_KEY, rowKey);
      return { alreadyExists: true };
    } catch {
      // Entity doesn't exist — create it
    }

    const entry: WaitlistEntry & { partitionKey: string; rowKey: string } = {
      partitionKey: PARTITION_KEY,
      rowKey,
      email,
      signedUpAt: new Date().toISOString(),
      source: "website",
    };
    await client.createEntity(entry);
    console.log(`[waitlist] Persisted to Azure Table Storage: ${email}`);
    return { alreadyExists: false };
  }

  // Fallback: in-memory
  if (memoryStore.has(email)) {
    return { alreadyExists: true };
  }
  memoryStore.add(email);
  console.log(`[waitlist] In-memory store (no AZURE_STORAGE_CONNECTION_STRING): ${email} (total: ${memoryStore.size})`);
  return { alreadyExists: false };
}
