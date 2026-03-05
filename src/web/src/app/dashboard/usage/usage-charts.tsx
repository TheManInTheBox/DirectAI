"use client";

import type { UsageByModel, DailyUsage } from "./actions";

function formatTokens(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(2)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`;
  return count.toLocaleString();
}

// Simple bar chart rendered with CSS — no chart library dependency
function UsageBarChart({ data }: { data: DailyUsage[] }) {
  if (data.length === 0) {
    return (
      <div className="text-zinc-500 text-sm py-8 text-center">
        No usage data yet. Make some API requests to see your usage here.
      </div>
    );
  }

  const maxTokens = Math.max(...data.map((d) => d.inputTokens + d.outputTokens), 1);

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-zinc-500 mb-2">
        <span>Last 30 days</span>
        <span>Peak: {formatTokens(maxTokens)} tokens/day</span>
      </div>
      <div className="flex items-end gap-[2px] h-32">
        {data.map((day) => {
          const total = day.inputTokens + day.outputTokens;
          const heightPercent = (total / maxTokens) * 100;
          const inputPercent = total > 0 ? (day.inputTokens / total) * 100 : 0;
          return (
            <div
              key={day.date}
              className="flex-1 relative group cursor-pointer"
              style={{ height: "100%" }}
            >
              <div
                className="absolute bottom-0 left-0 right-0 rounded-t-sm overflow-hidden transition-all"
                style={{ height: `${Math.max(heightPercent, 1)}%` }}
              >
                <div
                  className="bg-blue-500 w-full"
                  style={{ height: `${inputPercent}%` }}
                />
                <div
                  className="bg-indigo-400 w-full"
                  style={{ height: `${100 - inputPercent}%` }}
                />
              </div>
              {/* Tooltip */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                <div className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs whitespace-nowrap">
                  <div className="font-medium text-white">
                    {new Date(day.date).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                    })}
                  </div>
                  <div className="text-blue-400">
                    Input: {formatTokens(day.inputTokens)}
                  </div>
                  <div className="text-indigo-400">
                    Output: {formatTokens(day.outputTokens)}
                  </div>
                  <div className="text-zinc-400">
                    {day.requests.toLocaleString()} requests
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {/* Legend */}
      <div className="flex gap-4 text-xs text-zinc-400 mt-2">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-blue-500" />
          Input tokens
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-indigo-400" />
          Output tokens
        </div>
      </div>
    </div>
  );
}

function ModelBreakdownTable({ models }: { models: UsageByModel[] }) {
  if (models.length === 0) {
    return (
      <div className="text-zinc-500 text-sm py-4 text-center">
        No model usage this period.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-zinc-400">
            <th className="text-left py-2 pr-4">Model</th>
            <th className="text-left py-2 pr-4">Type</th>
            <th className="text-right py-2 pr-4">Input</th>
            <th className="text-right py-2 pr-4">Output</th>
            <th className="text-right py-2">Requests</th>
          </tr>
        </thead>
        <tbody>
          {models.map((m) => (
            <tr
              key={`${m.model}-${m.modality}`}
              className="border-b border-zinc-800/50 hover:bg-zinc-800/30"
            >
              <td className="py-2 pr-4 font-mono text-white">{m.model}</td>
              <td className="py-2 pr-4">
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    m.modality === "chat"
                      ? "bg-blue-500/20 text-blue-400"
                      : m.modality === "embedding"
                      ? "bg-green-500/20 text-green-400"
                      : "bg-purple-500/20 text-purple-400"
                  }`}
                >
                  {m.modality}
                </span>
              </td>
              <td className="py-2 pr-4 text-right text-zinc-300">
                {formatTokens(m.inputTokens)}
              </td>
              <td className="py-2 pr-4 text-right text-zinc-300">
                {formatTokens(m.outputTokens)}
              </td>
              <td className="py-2 text-right text-zinc-300">
                {m.requests.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function UsageCharts({
  dailyUsage,
  modelBreakdown,
}: {
  dailyUsage: DailyUsage[];
  modelBreakdown: UsageByModel[];
}) {
  return (
    <div className="space-y-8">
      {/* Daily usage chart */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">
          Daily Token Usage
        </h2>
        <UsageBarChart data={dailyUsage} />
      </div>

      {/* Model breakdown */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">
          Usage by Model
        </h2>
        <ModelBreakdownTable models={modelBreakdown} />
      </div>
    </div>
  );
}
