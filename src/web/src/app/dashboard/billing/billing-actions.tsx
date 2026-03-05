"use client";

import { useTransition, useState } from "react";
import { upgradeToManagedAction, manageSubscriptionAction } from "./actions";
import { ExternalLink } from "lucide-react";

export function BillingActions({
  currentTier,
  hasStripeCustomer,
}: {
  currentTier: string;
  hasStripeCustomer: boolean;
}) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const handleUpgrade = () => {
    setError(null);
    startTransition(async () => {
      try {
        await upgradeToManagedAction();
      } catch (e) {
        // redirect() throws a NEXT_REDIRECT error — don't catch it
        if (e instanceof Error && e.message === "NEXT_REDIRECT") throw e;
        setError(e instanceof Error ? e.message : "Failed to start checkout");
      }
    });
  };

  const handleManage = () => {
    setError(null);
    startTransition(async () => {
      try {
        await manageSubscriptionAction();
      } catch (e) {
        if (e instanceof Error && e.message === "NEXT_REDIRECT") throw e;
        setError(
          e instanceof Error ? e.message : "Failed to open billing portal"
        );
      }
    });
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg border border-red-700/50 bg-red-950/20 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        {currentTier === "open-source" && (
          <button
            onClick={handleUpgrade}
            disabled={isPending}
            className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
          >
            {isPending ? "Redirecting..." : "Upgrade to Managed — $3,000/mo"}
          </button>
        )}

        {currentTier === "managed" && (
          <a
            href="/waitlist"
            className="inline-flex items-center gap-2 rounded-lg border border-blue-600 px-6 py-2.5 text-sm font-semibold text-blue-400 transition hover:bg-blue-600/10"
          >
            Contact Sales for Enterprise
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}

        {hasStripeCustomer && currentTier !== "open-source" && (
          <button
            onClick={handleManage}
            disabled={isPending}
            className="rounded-lg border border-gray-700 px-6 py-2.5 text-sm text-gray-300 transition hover:border-gray-600 hover:text-white disabled:opacity-50"
          >
            {isPending ? "Redirecting..." : "Manage Subscription"}
          </button>
        )}
      </div>
    </div>
  );
}
