/**
 * Usage data server actions
 *
 * Queries the usage_records table to build usage stats for the dashboard.
 */
"use server";

import { auth } from "@/lib/auth";
import { getDb } from "@/lib/db";
import { usageRecords } from "@/lib/db/schema";
import { eq, and, gte, sql, desc } from "drizzle-orm";

export interface UsageSummary {
  totalInputTokens: number;
  totalOutputTokens: number;
  totalRequests: number;
  periodStart: string;
  periodEnd: string;
}

export interface UsageByModel {
  model: string;
  modality: string;
  inputTokens: number;
  outputTokens: number;
  requests: number;
}

export interface DailyUsage {
  date: string;
  inputTokens: number;
  outputTokens: number;
  requests: number;
}

/**
 * Get usage summary for the current billing period (calendar month).
 */
export async function getUsageSummary(): Promise<UsageSummary> {
  const session = await auth();
  if (!session?.user?.id) throw new Error("Unauthorized");

  const db = getDb();
  const now = new Date();
  const periodStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const periodEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);

  const [result] = await db
    .select({
      totalInputTokens: sql<number>`COALESCE(SUM(${usageRecords.inputTokens}), 0)`,
      totalOutputTokens: sql<number>`COALESCE(SUM(${usageRecords.outputTokens}), 0)`,
      totalRequests: sql<number>`COUNT(*)`,
    })
    .from(usageRecords)
    .where(
      and(
        eq(usageRecords.userId, session.user.id),
        gte(usageRecords.createdAt, periodStart)
      )
    );

  return {
    totalInputTokens: Number(result?.totalInputTokens ?? 0),
    totalOutputTokens: Number(result?.totalOutputTokens ?? 0),
    totalRequests: Number(result?.totalRequests ?? 0),
    periodStart: periodStart.toISOString(),
    periodEnd: periodEnd.toISOString(),
  };
}

/**
 * Get usage breakdown by model for the current billing period.
 */
export async function getUsageByModel(): Promise<UsageByModel[]> {
  const session = await auth();
  if (!session?.user?.id) throw new Error("Unauthorized");

  const db = getDb();
  const periodStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1);

  const rows = await db
    .select({
      model: usageRecords.model,
      modality: usageRecords.modality,
      inputTokens: sql<number>`COALESCE(SUM(${usageRecords.inputTokens}), 0)`,
      outputTokens: sql<number>`COALESCE(SUM(${usageRecords.outputTokens}), 0)`,
      requests: sql<number>`COUNT(*)`,
    })
    .from(usageRecords)
    .where(
      and(
        eq(usageRecords.userId, session.user.id),
        gte(usageRecords.createdAt, periodStart)
      )
    )
    .groupBy(usageRecords.model, usageRecords.modality)
    .orderBy(desc(sql`COUNT(*)`));

  return rows.map((r) => ({
    model: r.model,
    modality: r.modality,
    inputTokens: Number(r.inputTokens),
    outputTokens: Number(r.outputTokens),
    requests: Number(r.requests),
  }));
}

/**
 * Get daily usage for the last 30 days.
 */
export async function getDailyUsage(): Promise<DailyUsage[]> {
  const session = await auth();
  if (!session?.user?.id) throw new Error("Unauthorized");

  const db = getDb();
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  const rows = await db
    .select({
      date: sql<string>`DATE(${usageRecords.createdAt})`,
      inputTokens: sql<number>`COALESCE(SUM(${usageRecords.inputTokens}), 0)`,
      outputTokens: sql<number>`COALESCE(SUM(${usageRecords.outputTokens}), 0)`,
      requests: sql<number>`COUNT(*)`,
    })
    .from(usageRecords)
    .where(
      and(
        eq(usageRecords.userId, session.user.id),
        gte(usageRecords.createdAt, thirtyDaysAgo)
      )
    )
    .groupBy(sql`DATE(${usageRecords.createdAt})`)
    .orderBy(sql`DATE(${usageRecords.createdAt})`);

  return rows.map((r) => ({
    date: String(r.date),
    inputTokens: Number(r.inputTokens),
    outputTokens: Number(r.outputTokens),
    requests: Number(r.requests),
  }));
}
