import type { Metadata } from "next";
import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { users } from "@/lib/db/schema";
import { eq } from "drizzle-orm";
import { Check, Zap, Shield } from "lucide-react";
import { BillingActions } from "./billing-actions";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Billing",
  description: "Manage your DirectAI subscription and billing.",
};

const tierDetails: Record<
  string,
  {
    name: string;
    price: string;
    priceDetail: string;
    description: string;
    features: string[];
    badge: string;
  }
> = {
  free: {
    name: "Free",
    price: "Free",
    priceDetail: "$5 credit on shared API",
    description:
      "Self-host with our open-source stack, or try the shared API with $5 of free credit.",
    badge: "Current Plan",
    features: [
      "Full Helm chart & Bicep templates",
      "vLLM, ONNX Runtime, Whisper engines",
      "OpenAI-compatible API server",
      "$5 one-time API credit (shared cluster)",
      "20 RPM / 40K TPM rate limits",
      "Community support (GitHub Issues)",
      "Apache 2.0 license",
    ],
  },
  pro: {
    name: "Pro",
    price: "$50/mo",
    priceDetail: "+ per-token usage",
    description:
      "Instant API access on our shared GPU cluster. Low base fee plus per-token usage billing.",
    badge: "Current Plan",
    features: [
      "Shared GPU cluster (T4, A100)",
      "OpenAI-compatible API endpoint",
      "LLMs, embeddings, transcription",
      "300 RPM / 500K TPM rate limits",
      "Per-token usage billing via Stripe",
      "Dashboard & API key management",
      "Email support (48hr SLA)",
      "99.5% uptime SLA",
    ],
  },
  managed: {
    name: "Managed",
    price: "$3,500/mo",
    priceDetail: "+ per-token usage (2× Pro rates)",
    description:
      "Dedicated infrastructure in a DirectAI-owned Azure subscription. Fully isolated, fully managed.",
    badge: "Current Plan",
    features: [
      "Everything in Pro",
      "Dedicated Azure subscription",
      "Isolated infrastructure & networking",
      "Entra ID & Private Link integration",
      "Azure Monitor dashboards & alerts",
      "1,000 RPM / 5M TPM rate limits",
      "Email support (24hr SLA)",
      "99.9% uptime SLA",
    ],
  },
  enterprise: {
    name: "Enterprise",
    price: "Custom",
    priceDetail: "starting at $10K/mo",
    description:
      "Your Azure subscription, your rules. Flat management fee — no per-token metering. HIPAA/SOC 2 ready.",
    badge: "Current Plan",
    features: [
      "Everything in Managed",
      "Deploy into your own Azure subscription",
      "Flat fee — no usage metering",
      "Dedicated solutions engineer",
      "Custom model optimization & tuning",
      "HIPAA / SOC 2 compliance documentation",
      "Slack + phone support (1hr SLA)",
      "99.99% uptime SLA",
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

  const currentTier = user?.tier ?? "free";
  const details = tierDetails[currentTier] ?? tierDetails["free"];
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
                {details.badge}
              </span>
            </div>
            <p className="mt-1 text-2xl font-bold text-white">
              {details.price}
              {details.priceDetail && (
                <span className="ml-1 text-sm font-normal text-gray-400">
                  {details.priceDetail}
                </span>
              )}
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

      {/* Pro upsell for free users */}
      {currentTier === "free" && (
        <div className="rounded-xl border border-blue-500/30 bg-blue-950/10 p-6">
          <h3 className="font-semibold text-white">Why upgrade to Pro?</h3>
          <p className="mt-2 text-sm text-gray-400">
            Get instant API access on our shared GPU cluster. $50/mo base plus
            pay-per-token — start building production AI apps in minutes.
          </p>
          <ul className="mt-3 space-y-2 text-sm text-gray-300">
            <li>• OpenAI-compatible API — drop-in replacement, zero code changes</li>
            <li>• Shared GPU cluster with T4 and A100 capacity</li>
            <li>• LLM chat, embeddings, and transcription endpoints</li>
            <li>• 300 RPM / 500K TPM — 15× the Free tier limits</li>
            <li>• Usage dashboard, API key management, and billing portal</li>
            <li>• Email support with 48hr response SLA</li>
          </ul>
        </div>
      )}

      {/* Managed upsell for pro users */}
      {currentTier === "pro" && (
        <div className="rounded-xl border border-blue-500/30 bg-blue-950/10 p-6">
          <h3 className="font-semibold text-white">Need dedicated infrastructure?</h3>
          <p className="mt-2 text-sm text-gray-400">
            Upgrade to Managed — we deploy a fully isolated inference stack in a
            dedicated Azure subscription. Same API, higher limits, stronger SLA.
          </p>
          <ul className="mt-3 space-y-2 text-sm text-gray-300">
            <li>• Dedicated Azure subscription — complete data isolation</li>
            <li>• Entra ID & Private Link integration</li>
            <li>• 1,000 RPM / 5M TPM — 3× Pro limits</li>
            <li>• Azure Monitor dashboards & alerting</li>
            <li>• Email support with 24hr response SLA</li>
            <li>• 99.9% uptime SLA</li>
          </ul>
        </div>
      )}

      {/* Billing explainer */}
      <div className="rounded-lg border border-gray-800 bg-gray-900/30 px-5 py-4 text-sm text-gray-400">
        <p>
          <strong className="text-gray-300">How billing works:</strong>{" "}
          {currentTier === "enterprise" ? (
            <>You pay a flat management fee. GPU compute is billed directly by Azure through your Enterprise Agreement. DirectAI never touches your compute bill.</>
          ) : currentTier === "free" ? (
            <>The Free tier includes $5 of API credit on our shared cluster. Once exhausted, upgrade to Pro for continued access. Self-hosted deployments are always free.</>
          ) : (
            <>Your plan has a monthly base fee plus per-token usage charges. Usage is metered automatically and billed via Stripe at the end of each billing cycle.</>
          )}
        </p>
      </div>
    </div>
  );
}
