"use client";

import { useActionState } from "react";
import { joinWaitlist, type WaitlistResult } from "./actions";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";

export function WaitlistForm() {
  const [state, formAction, isPending] = useActionState<WaitlistResult | null, FormData>(
    joinWaitlist,
    null,
  );

  return (
    <div className="mx-auto w-full max-w-md">
      {state?.success ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-green-800/50 bg-green-950/30 p-8 text-center">
          <CheckCircle2 className="h-10 w-10 text-green-400" />
          <p className="text-lg font-semibold text-white">{state.message}</p>
        </div>
      ) : (
        <form action={formAction} className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              type="email"
              name="email"
              required
              placeholder="you@company.com"
              className="flex-1 rounded-lg border border-gray-700 bg-gray-900 px-4 py-3 text-sm text-white placeholder-gray-500 outline-none transition focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              disabled={isPending}
            />
            <button
              type="submit"
              disabled={isPending}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
            >
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Joining…
                </>
              ) : (
                "Join Waitlist"
              )}
            </button>
          </div>
          {state && !state.success && (
            <div className="flex items-center gap-2 text-sm text-red-400">
              <AlertCircle className="h-4 w-4" />
              {state.message}
            </div>
          )}
          <p className="text-xs text-gray-500">
            No spam. We&apos;ll only email you when it&apos;s time.
          </p>
        </form>
      )}
    </div>
  );
}
