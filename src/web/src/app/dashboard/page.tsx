import type { Metadata } from "next";
import Link from "next/link";
import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { apiKeys, users } from "@/lib/db/schema";
import { eq, and, isNull } from "drizzle-orm";
import { Key, CreditCard, Zap } from "lucide-react";

export const metadata: Metadata = {
  title: "Dashboard",
  description: "Manage your DirectAI API keys, usage, and billing.",
};

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  const db = getDb();

  // Parallel queries: active key count + user tier
  const [activeKeyRows, [user]] = await Promise.all([
    db
      .select({ id: apiKeys.id })
      .from(apiKeys)
      .where(and(eq(apiKeys.userId, session.user.id), isNull(apiKeys.revokedAt))),
    db
      .select({ tier: users.tier })
      .from(users)
      .where(eq(users.id, session.user.id))
      .limit(1),
  ]);

  const keyCount = activeKeyRows.length;
  const tier = user?.tier ?? "developer";

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">
          Welcome back
          {session.user.name ? `, ${session.user.name.split(" ")[0]}` : ""}
        </h1>
        <p className="mt-1 text-gray-400">
          Manage your API keys, monitor usage, and configure your account.
        </p>
      </div>

      {/* Quick stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          title="API Keys"
          value={keyCount.toString()}
          subtitle="active keys"
          icon={<Key className="h-5 w-5" />}
          href="/dashboard/api-keys"
        />
        <StatCard
          title="Current Plan"
          value={tier}
          subtitle="tier"
          icon={<CreditCard className="h-5 w-5" />}
          href="/dashboard/billing"
        />
        <StatCard
          title="Requests"
          value="—"
          subtitle="this month"
          icon={<Zap className="h-5 w-5" />}
        />
      </div>

      {/* Quick actions */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-white">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/dashboard/api-keys"
            className="rounded-lg border border-gray-700 bg-gray-900 px-4 py-2.5 text-sm text-gray-300 transition hover:border-gray-600 hover:text-white"
          >
            Create API Key
          </Link>
          <Link
            href="/dashboard/billing"
            className="rounded-lg border border-gray-700 bg-gray-900 px-4 py-2.5 text-sm text-gray-300 transition hover:border-gray-600 hover:text-white"
          >
            Manage Billing
          </Link>
        </div>
      </div>

      {/* Getting started */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
        <h2 className="text-lg font-semibold text-white">Getting Started</h2>
        <p className="mt-2 text-sm text-gray-400">
          Use any OpenAI-compatible SDK. Just point it at DirectAI:
        </p>
        <pre className="mt-4 overflow-x-auto rounded-lg bg-gray-950 p-4 font-mono text-sm text-gray-300">
{`from openai import OpenAI

client = OpenAI(
    base_url="https://api.agilecloud.ai/v1",
    api_key="YOUR_API_KEY",
)

response = client.chat.completions.create(
    model="llama-3.1-70b-instruct",
    messages=[{"role": "user", "content": "Hello!"}],
)`}
        </pre>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  icon,
  href,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
  href?: string;
}) {
  const cls =
    "rounded-xl border border-gray-800 bg-gray-900/50 p-6 transition hover:border-gray-700";

  const inner = (
    <>
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">{title}</p>
        <div className="text-gray-500">{icon}</div>
      </div>
      <p className="mt-2 text-2xl font-bold capitalize text-white">{value}</p>
      <p className="mt-1 text-xs text-gray-500">{subtitle}</p>
    </>
  );

  if (href) {
    return (
      <Link href={href} className={`block ${cls}`}>
        {inner}
      </Link>
    );
  }
  return <div className={cls}>{inner}</div>;
}
