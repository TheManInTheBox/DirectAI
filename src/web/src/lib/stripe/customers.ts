/**
 * Stripe Customer Sync
 *
 * Creates a Stripe customer for a new user and links the customer ID
 * back to the users table. Called from the NextAuth createUser event.
 */

import { eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { users } from "@/lib/db/schema";
import { stripe } from "./client";

/**
 * Create a Stripe customer for a new DirectAI user.
 * Stores the stripeCustomerId in the users table.
 *
 * Idempotent — if the user already has a stripeCustomerId, this is a no-op.
 */
export async function createStripeCustomer(userId: string, email: string, name?: string | null) {
  // Check if user already has a Stripe customer
  const [user] = await db
    .select({ stripeCustomerId: users.stripeCustomerId })
    .from(users)
    .where(eq(users.id, userId))
    .limit(1);

  if (user?.stripeCustomerId) {
    return user.stripeCustomerId;
  }

  // Create Stripe customer
  const customer = await stripe.customers.create({
    email,
    name: name ?? undefined,
    metadata: {
      directai_user_id: userId,
    },
  });

  // Link back to user record
  await db
    .update(users)
    .set({
      stripeCustomerId: customer.id,
      updatedAt: new Date(),
    })
    .where(eq(users.id, userId));

  return customer.id;
}

/**
 * Get or create a Stripe Checkout Session for tier upgrade.
 *
 * @param userId - DirectAI user ID
 * @param priceId - Stripe Price ID for the target tier
 * @param successUrl - Redirect URL after successful payment
 * @param cancelUrl - Redirect URL if user cancels
 */
export async function createCheckoutSession(
  userId: string,
  priceId: string,
  successUrl: string,
  cancelUrl: string
) {
  // Get user's Stripe customer ID
  const [user] = await db
    .select({
      stripeCustomerId: users.stripeCustomerId,
      email: users.email,
      name: users.name,
    })
    .from(users)
    .where(eq(users.id, userId))
    .limit(1);

  if (!user) {
    throw new Error(`User ${userId} not found`);
  }

  // Ensure Stripe customer exists
  const customerId = user.stripeCustomerId
    ?? await createStripeCustomer(userId, user.email, user.name);

  // Create checkout session
  const session = await stripe.checkout.sessions.create({
    customer: customerId,
    mode: "subscription",
    line_items: [{ price: priceId, quantity: 1 }],
    success_url: successUrl,
    cancel_url: cancelUrl,
    metadata: {
      directai_user_id: userId,
    },
  });

  return session;
}

/**
 * Get a Stripe Customer Portal URL for subscription management.
 */
export async function createPortalSession(
  stripeCustomerId: string,
  returnUrl: string
) {
  const session = await stripe.billingPortal.sessions.create({
    customer: stripeCustomerId,
    return_url: returnUrl,
  });

  return session.url;
}
