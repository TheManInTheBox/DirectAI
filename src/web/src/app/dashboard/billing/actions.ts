/**
 * Billing Server Actions
 *
 * Upgrade to Pro via Stripe Checkout, or manage existing subscription
 * via Stripe Customer Portal. Both redirect the browser.
 */
"use server";

import { auth } from "@/lib/auth";
import { getDb } from "@/lib/db";
import { users } from "@/lib/db/schema";
import { eq } from "drizzle-orm";
import { createCheckoutSession, createPortalSession } from "@/lib/stripe/customers";
import { redirect } from "next/navigation";
import { headers } from "next/headers";

async function getBaseUrl(): Promise<string> {
  const h = await headers();
  const host = h.get("host") ?? "agilecloud.ai";
  const proto = h.get("x-forwarded-proto") ?? "https";
  return `${proto}://${host}`;
}

export async function upgradeToProAction() {
  const session = await auth();
  if (!session?.user?.id) throw new Error("Unauthorized");

  const proPriceId = process.env.STRIPE_PRO_PRICE_ID;
  if (!proPriceId) throw new Error("Stripe Pro price not configured");

  const baseUrl = await getBaseUrl();

  const checkoutSession = await createCheckoutSession(
    session.user.id,
    proPriceId,
    `${baseUrl}/dashboard/billing?upgraded=true`,
    `${baseUrl}/dashboard/billing`,
  );

  if (checkoutSession.url) {
    redirect(checkoutSession.url);
  }
  throw new Error("Failed to create checkout session");
}

export async function manageSubscriptionAction() {
  const session = await auth();
  if (!session?.user?.id) throw new Error("Unauthorized");

  const db = getDb();
  const [user] = await db
    .select({ stripeCustomerId: users.stripeCustomerId })
    .from(users)
    .where(eq(users.id, session.user.id))
    .limit(1);

  if (!user?.stripeCustomerId) {
    throw new Error("No billing account found");
  }

  const baseUrl = await getBaseUrl();

  const portalUrl = await createPortalSession(
    user.stripeCustomerId,
    `${baseUrl}/dashboard/billing`,
  );

  if (portalUrl) {
    redirect(portalUrl);
  }
  throw new Error("Failed to create portal session");
}
