/**
 * Stripe Webhook Handler
 *
 * Processes Stripe events and updates DirectAI state accordingly.
 * Mounted at POST /api/webhooks/stripe.
 *
 * Events handled:
 *   - checkout.session.completed  → Activate subscription, update user tier
 *   - customer.subscription.updated → Tier changes, cancellations
 *   - customer.subscription.deleted → Downgrade to free tier
 *   - invoice.payment_failed      → Mark subscription past due
 */

import { NextResponse } from "next/server";
import { headers } from "next/headers";
import Stripe from "stripe";
import { eq } from "drizzle-orm";
import { stripe } from "@/lib/stripe/client";
import { db } from "@/lib/db";
import { users } from "@/lib/db/schema";

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

  try {
    switch (event.type) {
      case "checkout.session.completed":
        await handleCheckoutCompleted(event.data.object as Stripe.Checkout.Session);
        break;

      case "customer.subscription.updated":
        await handleSubscriptionUpdated(event.data.object as Stripe.Subscription);
        break;

      case "customer.subscription.deleted":
        await handleSubscriptionDeleted(event.data.object as Stripe.Subscription);
        break;

      case "invoice.payment_failed":
        await handlePaymentFailed(event.data.object as Stripe.Invoice);
        break;

      default:
        // Unhandled event type — log and acknowledge
        console.log(`[stripe-webhook] Unhandled event type: ${event.type}`);
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error(`[stripe-webhook] Error handling ${event.type}: ${message}`);
    // Return 200 to prevent Stripe from retrying (we'll investigate via logs)
    // Returning 5xx would cause Stripe to retry, which could cause duplicate processing
  }

  return NextResponse.json({ received: true });
}

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------

async function handleCheckoutCompleted(session: Stripe.Checkout.Session) {
  const userId = session.metadata?.directai_user_id;
  if (!userId) {
    console.error("[stripe-webhook] checkout.session.completed missing directai_user_id");
    return;
  }

  // Determine tier from the subscription price
  const tier = await getTierFromSubscription(session.subscription as string);

  await db
    .update(users)
    .set({
      tier,
      stripeCustomerId: session.customer as string,
      updatedAt: new Date(),
    })
    .where(eq(users.id, userId));

  console.log(`[stripe-webhook] User ${userId} upgraded to ${tier}`);
}

async function handleSubscriptionUpdated(subscription: Stripe.Subscription) {
  const customerId = subscription.customer as string;

  // Find user by Stripe customer ID
  const [user] = await db
    .select({ id: users.id })
    .from(users)
    .where(eq(users.stripeCustomerId, customerId))
    .limit(1);

  if (!user) {
    console.error(`[stripe-webhook] No user found for Stripe customer ${customerId}`);
    return;
  }

  const tier = mapPriceToTier(subscription.items.data[0]?.price?.id);

  await db
    .update(users)
    .set({ tier, updatedAt: new Date() })
    .where(eq(users.id, user.id));

  console.log(`[stripe-webhook] User ${user.id} subscription updated to ${tier}`);
}

async function handleSubscriptionDeleted(subscription: Stripe.Subscription) {
  const customerId = subscription.customer as string;

  const [user] = await db
    .select({ id: users.id })
    .from(users)
    .where(eq(users.stripeCustomerId, customerId))
    .limit(1);

  if (!user) {
    console.error(`[stripe-webhook] No user found for Stripe customer ${customerId}`);
    return;
  }

  // Downgrade to open-source (free) tier
  await db
    .update(users)
    .set({ tier: "open-source", updatedAt: new Date() })
    .where(eq(users.id, user.id));

  console.log(`[stripe-webhook] User ${user.id} downgraded to open-source (subscription deleted)`);
}

async function handlePaymentFailed(invoice: Stripe.Invoice) {
  const customerId = invoice.customer as string;
  console.warn(`[stripe-webhook] Payment failed for customer ${customerId}, invoice ${invoice.id}`);
  // TODO: Send notification email, grace period logic
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function getTierFromSubscription(subscriptionId: string): Promise<string> {
  const subscription = await stripe.subscriptions.retrieve(subscriptionId);
  const priceId = subscription.items.data[0]?.price?.id;
  return mapPriceToTier(priceId);
}

/**
 * Map a Stripe Price ID to a DirectAI tier name.
 * Configure these in environment variables once Stripe products are created.
 *
 * Tiers:
 *   open-source  — Free forever (no Stripe subscription)
 *   managed      — $3,000/mo management fee
 *   enterprise   — Custom contract ($10K+/mo)
 */
function mapPriceToTier(priceId?: string): string {
  const managedPriceId = process.env.STRIPE_MANAGED_PRICE_ID;
  const enterprisePriceId = process.env.STRIPE_ENTERPRISE_PRICE_ID;

  if (priceId === managedPriceId) return "managed";
  if (priceId === enterprisePriceId) return "enterprise";
  return "open-source";
}
