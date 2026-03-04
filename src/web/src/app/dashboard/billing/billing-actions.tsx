"use client";

import { useTransition, useState } from "react";
import { upgradeToProAction, manageSubscriptionAction } from "./actions";

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
        await upgradeToProAction();
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
        {currentTier === "developer" && (
          <button
            onClick={handleUpgrade}
            disabled={isPending}
            className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
          >
            {isPending ? "Redirecting..." : "Upgrade to Pro — $49/mo"}
          </button>
        )}

        {hasStripeCustomer && (
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
