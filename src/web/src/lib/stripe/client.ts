/**
 * Stripe Client — Server-side only
 *
 * Lazy singleton Stripe instance for server actions and API routes.
 * Never import this in client components.
 *
 * Environment variables:
 *   STRIPE_SECRET_KEY       — Stripe API secret key
 *   STRIPE_WEBHOOK_SECRET   — Webhook endpoint signing secret
 */

import Stripe from "stripe";

let _stripe: Stripe | undefined;

export function getStripe(): Stripe {
  if (!_stripe) {
    if (!process.env.STRIPE_SECRET_KEY) {
      throw new Error("STRIPE_SECRET_KEY is not set");
    }
    _stripe = new Stripe(process.env.STRIPE_SECRET_KEY, {
      apiVersion: "2026-02-25.clover",
      typescript: true,
      appInfo: {
        name: "DirectAI",
        url: "https://agilecloud.ai",
      },
    });
  }
  return _stripe;
}

/** Convenience re-export — lazy, throws at call time if STRIPE_SECRET_KEY is missing. */
export const stripe = new Proxy({} as Stripe, {
  get(_target, prop) {
    return (getStripe() as unknown as Record<string | symbol, unknown>)[prop];
  },
});

/**
 * Stripe Meter event names — must match meters configured in Stripe Dashboard.
 */
export const STRIPE_METERS = {
  /** Token usage for LLM/embedding/STT inference. */
  TOKENS: process.env.STRIPE_METER_ID_TOKENS ?? "directai_token_usage",
} as const;
