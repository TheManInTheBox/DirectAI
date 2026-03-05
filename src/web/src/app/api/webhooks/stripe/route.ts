/**
 * Stripe Webhook Handler
 *
 * Processes Stripe events and updates DirectAI state accordingly.
 * Mounted at POST /api/webhooks/stripe.
 *
 * Events handled:
 *   - checkout.session.completed      → Activate subscription, update user tier
 *   - customer.subscription.updated   → Tier changes (plan swap, cancellation pending)
 *   - customer.subscription.deleted   → Downgrade to free tier
 *   - invoice.payment_failed          → Log warning (grace period / notification TBD)
 *
 * Tier mapping (env vars → tier names):
 *   STRIPE_PRO_PRICE_ID        → "pro"       ($50/mo + metered usage)
 *   STRIPE_MANAGED_PRICE_ID    → "managed"   ($3,500/mo + metered usage)
 *   STRIPE_ENTERPRISE_PRICE_ID → "enterprise" (custom flat fee)
 *   (no subscription)          → "free"       ($0 / self-hosted OSS)
 */

import { NextResponse } from "next/server";
import { headers } from "next/headers";
import Stripe from "stripe";
import { eq } from "drizzle-orm";
import { stripe } from "@/lib/stripe/client";
import { getDb } from "@/lib/db";
import { users } from "@/lib/db/schema";

// Valid DirectAI tier values — must match DB column constraints and dashboard UI
type DirectAITier = "free" | "pro" | "managed" | "enterprise";

export async function POST(req: Request) {
  const body = await req.text();
  const headerList = await headers();
  const signature = headerList.get("stripe-signature");

  if (!signature) {
    return NextResponse.json(
      { error: "Missing stripe-signature header" },
      { status: 400 }
    );
  }

  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    console.error("[stripe-webhook] STRIPE_WEBHOOK_SECRET is not set");
    return NextResponse.json(
      { error: "Webhook secret not configured" },
      { status: 500 }
    );
  }

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(body, signature, webhookSecret);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error(`[stripe-webhook] Signature verification failed: ${message}`);
    return NextResponse.json(
      { error: "Invalid signature" },
      { status: 400 }
    );
  }

  console.log(`[stripe-webhook] Received event: ${event.type} (${event.id})`);

  try {
    switch (event.type) {
      case "checkout.session.completed":
        await handleCheckoutCompleted(
          event.data.object as Stripe.Checkout.Session
        );
        break;

      case "customer.subscription.updated":
        await handleSubscriptionUpdated(
          event.data.object as Stripe.Subscription
        );
        break;

      case "customer.subscription.deleted":
        await handleSubscriptionDeleted(
          event.data.object as Stripe.Subscription
        );
        break;

      case "invoice.payment_failed":
        await handlePaymentFailed(event.data.object as Stripe.Invoice);
        break;

      default:
        console.log(`[stripe-webhook] Unhandled event type: ${event.type}`);
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error(`[stripe-webhook] Error handling ${event.type}: ${message}`);
    // Return 200 anyway — retries on 5xx cause duplicate processing.
    // We investigate failures via structured logs.
  }

  return NextResponse.json({ received: true });
}

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------

/**
 * checkout.session.completed
 *
 * Fires when the customer finishes Stripe Checkout.
 * The session metadata carries `directai_user_id` so we know who paid.
 * We resolve the subscription's price to determine the tier.
 */
async function handleCheckoutCompleted(session: Stripe.Checkout.Session) {
  const userId = session.metadata?.directai_user_id;
  if (!userId) {
    console.error(
      "[stripe-webhook] checkout.session.completed missing directai_user_id in metadata"
    );
    return;
  }

  if (!session.subscription) {
    console.error(
      `[stripe-webhook] checkout.session.completed for user ${userId} has no subscription`
    );
    return;
  }

  const tier = await getTierFromSubscription(session.subscription as string);
  const db = getDb();

  await db
    .update(users)
    .set({
      tier,
      stripeCustomerId: session.customer as string,
      updatedAt: new Date(),
    })
    .where(eq(users.id, userId));

  console.log(
    `[stripe-webhook] User ${userId} upgraded to ${tier} (subscription: ${session.subscription})`
  );
}

/**
 * customer.subscription.updated
 *
 * Fires on plan changes, cancellation scheduling (cancel_at_period_end),
 * and reactivation. We re-resolve the price → tier and update the DB.
 *
 * When cancel_at_period_end is true the subscription is still active —
 * the actual downgrade happens on customer.subscription.deleted.
 */
async function handleSubscriptionUpdated(subscription: Stripe.Subscription) {
  const customerId = subscription.customer as string;
  const db = getDb();

  const [user] = await db
    .select({ id: users.id, tier: users.tier })
    .from(users)
    .where(eq(users.stripeCustomerId, customerId))
    .limit(1);

  if (!user) {
    console.error(
      `[stripe-webhook] subscription.updated — no user for customer ${customerId}`
    );
    return;
  }

  // If the subscription is no longer active (canceled, unpaid, past_due),
  // downgrade to free immediately rather than waiting for the deleted event.
  if (
    subscription.status === "canceled" ||
    subscription.status === "unpaid"
  ) {
    await db
      .update(users)
      .set({ tier: "free", updatedAt: new Date() })
      .where(eq(users.id, user.id));
    console.log(
      `[stripe-webhook] User ${user.id} downgraded to free (subscription status: ${subscription.status})`
    );
    return;
  }

  // Active or trialing — resolve the current price to a tier
  const tier = mapPriceToTier(subscription.items.data[0]?.price?.id);

  if (tier !== user.tier) {
    await db
      .update(users)
      .set({ tier, updatedAt: new Date() })
      .where(eq(users.id, user.id));
    console.log(
      `[stripe-webhook] User ${user.id} tier changed: ${user.tier} → ${tier}`
    );
  } else {
    console.log(
      `[stripe-webhook] User ${user.id} subscription updated, tier unchanged (${tier})`
    );
  }
}

/**
 * customer.subscription.deleted
 *
 * Fires when the subscription is fully terminated (after any grace period).
 * Unconditionally downgrade to free.
 */
async function handleSubscriptionDeleted(subscription: Stripe.Subscription) {
  const customerId = subscription.customer as string;
  const db = getDb();

  const [user] = await db
    .select({ id: users.id })
    .from(users)
    .where(eq(users.stripeCustomerId, customerId))
    .limit(1);

  if (!user) {
    console.error(
      `[stripe-webhook] subscription.deleted — no user for customer ${customerId}`
    );
    return;
  }

  await db
    .update(users)
    .set({ tier: "free", updatedAt: new Date() })
    .where(eq(users.id, user.id));

  console.log(
    `[stripe-webhook] User ${user.id} downgraded to free (subscription deleted)`
  );
}

/**
 * invoice.payment_failed
 *
 * Log the failure. Stripe will retry per your retry settings.
 * TODO: Send the customer a notification email.
 * TODO: Grace period logic — don't downgrade until N retries exhausted.
 */
async function handlePaymentFailed(invoice: Stripe.Invoice) {
  const customerId = invoice.customer as string;
  console.warn(
    `[stripe-webhook] Payment failed for customer ${customerId}, invoice ${invoice.id}`
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Retrieve a subscription from Stripe and resolve its price to a tier.
 */
async function getTierFromSubscription(
  subscriptionId: string
): Promise<DirectAITier> {
  const subscription = await stripe.subscriptions.retrieve(subscriptionId);
  const priceId = subscription.items.data[0]?.price?.id;
  return mapPriceToTier(priceId);
}

/**
 * Map a Stripe Price ID to a DirectAI tier name.
 *
 * Env vars (set these after creating Stripe Products):
 *   STRIPE_PRO_PRICE_ID        → "pro"        ($50/mo + metered)
 *   STRIPE_MANAGED_PRICE_ID    → "managed"     ($3,500/mo + metered)
 *   STRIPE_ENTERPRISE_PRICE_ID → "enterprise"  (custom flat fee)
 *
 * Unknown or missing price ID falls through to "free" — safe default
 * because free users have no subscription (this path shouldn't fire
 * in practice, but we never leave a user in an undefined tier state).
 */
function mapPriceToTier(priceId?: string): DirectAITier {
  if (!priceId) return "free";

  const proPriceId = process.env.STRIPE_PRO_PRICE_ID;
  const managedPriceId = process.env.STRIPE_MANAGED_PRICE_ID;
  const enterprisePriceId = process.env.STRIPE_ENTERPRISE_PRICE_ID;

  if (priceId === proPriceId) return "pro";
  if (priceId === managedPriceId) return "managed";
  if (priceId === enterprisePriceId) return "enterprise";

  console.warn(
    `[stripe-webhook] Unknown price ID: ${priceId} — defaulting to free`
  );
  return "free";
}
