/**
 * Stripe integration barrel export.
 *
 * Usage:
 *   import { stripe, createStripeCustomer, createCheckoutSession } from "@/lib/stripe";
 */

export { stripe, STRIPE_METERS } from "./client";
export {
  createStripeCustomer,
  createCheckoutSession,
  createPortalSession,
} from "./customers";
