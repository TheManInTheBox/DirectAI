import type { Metadata } from "next";
import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { users } from "@/lib/db/schema";
import { eq } from "drizzle-orm";
import { Check, Zap, Shield } from "lucide-react";
import { BillingActions } from "./billing-actions";

export const metadata: Metadata = {
  title: "Billing",
  description: "Manage your DirectAI subscription and billing.",
};

const tierDetails: Record<
  string,
  {
    name: string;
    price: string;
    description: string;
    features: string[];
  }
> = {
  developer: {
    name: "Developer",
    price: "Free",
    description: "$5/month in free credits. Shared GPU pool.",
    features: [
      "60 RPM / 100K TPM",
      "$5/mo free credits",
      "Community support",
      "Best-effort SLA",
    ],
  },
  pro: {
    name: "Pro",
    price: "$49/mo",
    description: "$50/month included credits. Priority GPU access.",
    features: [
      "600 RPM / 1M TPM",
      "$50/mo included credits",
      "Email support (24hr SLA)",
      "99.9% SLA",
      "Fine-tuned models",
    ],
  },
  enterprise: {
    name: "Enterprise",
    price: "Custom",
    description: "Dedicated infrastructure. Full isolation.",
    features: [
      "Unlimited RPM",
      "Dedicated GPU pools",
      "Slack + phone support (1hr SLA)",
      "99.99% SLA",
      "Custom models",
    ],
  },
};

export default async function BillingPage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  const db = getDb();
  const [user] = await db
    .select({
      tier: users.tier,
      stripeCustomerId: users.stripeCustomerId,
    })
    .from(users)
    .where(eq(users.id, session.user.id))
    .limit(1);

  const currentTier = user?.tier ?? "developer";
  const details = tierDetails[currentTier] ?? tierDetails.developer;
  const hasStripeCustomer = !!user?.stripeCustomerId;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Billing</h1>
        <p className="mt-1 text-gray-400">
          Manage your subscription plan and payment method.
        </p>
      </div>

      {/* Current plan card */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-white">
                {details.name}
              </h2>
              <span className="rounded-full bg-blue-600/20 px-2.5 py-0.5 text-xs font-medium text-blue-400">
                Current Plan
              </span>
            </div>
            <p className="mt-1 text-2xl font-bold text-white">
              {details.price}
            </p>
            <p className="mt-1 text-sm text-gray-400">{details.description}</p>
          </div>
          <div className="text-gray-500">
            {currentTier === "enterprise" ? (
              <Shield className="h-8 w-8" />
            ) : (
              <Zap className="h-8 w-8" />
            )}
          </div>
        </div>

        <ul className="mt-6 space-y-2">
          {details.features.map((feature) => (
            <li
              key={feature}
              className="flex items-center gap-2 text-sm text-gray-300"
            >
              <Check className="h-4 w-4 text-blue-400" />
              {feature}
            </li>
          ))}
        </ul>
      </div>

      {/* Upgrade / manage actions */}
      <BillingActions
        currentTier={currentTier}
        hasStripeCustomer={hasStripeCustomer}
      />

      {/* Pro upsell */}
      {currentTier === "developer" && (
        <div className="rounded-xl border border-blue-500/30 bg-blue-950/10 p-6">
          <h3 className="font-semibold text-white">Why upgrade to Pro?</h3>
          <ul className="mt-3 space-y-2 text-sm text-gray-300">
            <li>• 10× higher rate limits (600 RPM / 1M TPM)</li>
            <li>• $50/month in included credits (vs $5)</li>
            <li>• Priority GPU queue — lower latency under load</li>
            <li>• Deploy fine-tuned models</li>
            <li>• 99.9% SLA guarantee</li>
            <li>• Email support with 24hr response SLA</li>
          </ul>
        </div>
      )}
    </div>
  );
}
