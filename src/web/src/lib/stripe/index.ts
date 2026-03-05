/**
 * Stripe integration barrel export.
 *
 * Usage:
 *   import { stripe, createStripeCustomer, createCheckoutSession } from "@/lib/stripe";
 */

export { stripe } from "./client";
export {
  createStripeCustomer,
  createCheckoutSession,
  createPortalSession,
} from "./customers";
