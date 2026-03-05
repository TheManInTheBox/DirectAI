import type { Metadata } from "next";
import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { getDb } from "@/lib/db";
import { users } from "@/lib/db/schema";
import { eq } from "drizzle-orm";
import { Check, Zap, Shield, ExternalLink } from "lucide-react";
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
    badge: string;
  }
> = {
  "open-source": {
    name: "Open Source",
    price: "Free",
    description: "Self-managed deployment via Helm + Bicep. Apache 2.0 licensed.",
    badge: "Free Forever",
    features: [
      "Full inference stack (vLLM, ONNX Runtime, TRT-LLM)",
      "Helm chart + Bicep IaC",
      "Community support (GitHub Issues)",
      "Best-effort SLA",
      "No vendor lock-in — Apache 2.0",
    ],
  },
  managed: {
    name: "Managed",
    price: "$3,000/mo",
    description:
      "DirectAI deploys and manages inference inside your Azure subscription. You pay Azure for compute.",
    badge: "Current Plan",
    features: [
      "Deployed into your Azure subscription",
      "Data never leaves your boundary",
      "All open-source models + fine-tuned",
      "Email support (24hr SLA)",
      "99.9% uptime SLA",
      "Azure Monitor + Entra ID integrated",
    ],
  },
  enterprise: {
    name: "Enterprise",
    price: "Custom",
    description: "Dedicated solutions engineering. HIPAA/SOC 2 documentation provided.",
    badge: "Current Plan",
    features: [
      "Everything in Managed",
      "Dedicated solutions engineer",
      "Custom model optimization",
      "Slack + phone support (1hr SLA)",
      "99.99% uptime SLA",
      "HIPAA BAA + SOC 2 documentation",
      "Multi-region deployment",
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

  const currentTier = user?.tier ?? "open-source";
  const details = tierDetails[currentTier] ?? tierDetails["open-source"];
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

      {/* Managed upsell for open-source users */}
      {currentTier === "open-source" && (
        <div className="rounded-xl border border-blue-500/30 bg-blue-950/10 p-6">
          <h3 className="font-semibold text-white">Why upgrade to Managed?</h3>
          <p className="mt-2 text-sm text-gray-400">
            Stop spending engineering time on GPU infrastructure. We deploy and
            manage the full inference stack inside your Azure subscription.
          </p>
          <ul className="mt-3 space-y-2 text-sm text-gray-300">
            <li>• DirectAI deploys into your Azure subscription — zero data egress</li>
            <li>• Production-grade autoscaling, monitoring, and alerting</li>
            <li>• Azure Monitor + Entra ID integrated out of the box</li>
            <li>• Email support with 24hr response SLA</li>
            <li>• 99.9% uptime SLA guarantee</li>
            <li>• You pay Azure for GPU compute — we charge $3K/mo management fee only</li>
          </ul>
        </div>
      )}

      {/* Azure compute note */}
      <div className="rounded-lg border border-gray-800 bg-gray-900/30 px-5 py-4 text-sm text-gray-400">
        <p>
          <strong className="text-gray-300">How billing works:</strong>{" "}
          DirectAI charges a flat management fee for deployment, monitoring, and
          support. GPU compute costs are billed directly by Azure through your
          existing Enterprise Agreement or MCA. DirectAI never touches your
          compute bill.
        </p>
      </div>
    </div>
  );
}
