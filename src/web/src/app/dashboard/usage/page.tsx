import type { Metadata } from "next";
import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { getUsageSummary, getUsageByModel, getDailyUsage } from "./actions";
import { UsageCharts } from "./usage-charts";
import { Activity, ArrowUpRight, ArrowDownRight, Hash } from "lucide-react";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Usage — DirectAI",
  description: "Monitor your API token consumption and request volume.",
};

function formatTokens(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(2)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return count.toLocaleString();
}

export default async function UsagePage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  const [summary, modelBreakdown, dailyUsage] = await Promise.all([
    getUsageSummary(),
    getUsageByModel(),
    getDailyUsage(),
  ]);

  const periodLabel = new Date(summary.periodStart).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Usage</h1>
        <p className="text-zinc-400 mt-1">
          Current billing period: <span className="text-zinc-300">{periodLabel}</span>
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
          <div className="flex items-center gap-2 text-zinc-400 text-sm">
            <ArrowUpRight className="h-4 w-4 text-blue-400" />
            Input Tokens
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            {formatTokens(summary.totalInputTokens)}
          </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
          <div className="flex items-center gap-2 text-zinc-400 text-sm">
            <ArrowDownRight className="h-4 w-4 text-indigo-400" />
            Output Tokens
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            {formatTokens(summary.totalOutputTokens)}
          </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5">
          <div className="flex items-center gap-2 text-zinc-400 text-sm">
            <Hash className="h-4 w-4 text-green-400" />
            Total Requests
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            {summary.totalRequests.toLocaleString()}
          </div>
        </div>
      </div>

      {/* Charts */}
      <UsageCharts dailyUsage={dailyUsage} modelBreakdown={modelBreakdown} />

      {/* Billing estimate note */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 text-sm text-zinc-400">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4" />
          <span>
            Usage data updates in near real-time. Final billing amounts may differ slightly
            due to rounding. View your invoices on the{" "}
            <a href="/dashboard/billing" className="text-blue-400 hover:underline">
              billing page
            </a>
            .
          </span>
        </div>
      </div>
    </div>
  );
}
