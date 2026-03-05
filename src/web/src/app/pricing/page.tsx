import type { Metadata } from "next";
import Link from "next/link";
import { Check, ArrowRight, GitBranch, Zap } from "lucide-react";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "From self-hosted open-source to fully managed enterprise inference — deploy AI models on Azure with zero vendor lock-in.",
};

interface Tier {
  name: string;
  price: string;
  priceDetail: string;
  description: string;
  cta: string;
  ctaHref: string;
  highlighted: boolean;
  badge?: string;
  features: string[];
}

const tiers: Tier[] = [
  {
    name: "Free",
    price: "Free",
    priceDetail: "forever",
    description:
      "Helm charts, Bicep templates, and model configs to deploy AI inference on your own AKS cluster. Community support via GitHub.",
    cta: "View on GitHub",
    ctaHref: "https://github.com/TheManInTheBox/DirectAI",
    highlighted: false,
    features: [
      "Full Helm chart & Bicep templates",
      "vLLM, ONNX Runtime, Whisper engines",
      "OpenAI-compatible API server",
      "GPU autoscaling (KEDA + Cluster Autoscaler)",
      "Model deployment configs",
      "Community support (GitHub Issues)",
      "Apache 2.0 license",
    ],
  },
  {
    name: "Pro",
    price: "$499",
    priceDetail: "/month",
    description:
      "Instant access to our shared GPU cluster. OpenAI-compatible API at api.agilecloud.ai — no infrastructure to manage. Start building in minutes.",
    cta: "Get Started",
    ctaHref: "/waitlist",
    highlighted: true,
    badge: "Best for Developers",
    features: [
      "Shared GPU cluster (T4, A100)",
      "OpenAI-compatible API endpoint",
      "LLMs, embeddings, transcription",
      "300 RPM / 500K TPM rate limits",
      "Dashboard & API key management",
      "Usage analytics & billing",
      "Email support (48hr SLA)",
      "99.5% uptime SLA",
    ],
  },
  {
    name: "Managed",
    price: "$3K",
    priceDetail: "/month + your Azure compute",
    description:
      "DirectAI deploys and manages inference inside your Azure subscription. You pay Azure for compute via your EA. We handle the rest.",
    cta: "Talk to an Engineer",
    ctaHref: "/waitlist",
    highlighted: false,
    features: [
      "Everything in Pro",
      "Dedicated Azure subscription",
      "Deployment into your Azure subscription",
      "Entra ID & Private Link integration",
      "Azure Monitor dashboards & alerts",
      "Scaling configuration & optimization",
      "Model updates & security patches",
      "Email support (24hr SLA)",
      "99.9% uptime SLA",
    ],
  },
  {
    name: "Enterprise",
    price: "Custom",
    priceDetail: "starting at $10K/month",
    description:
      "Your Azure subscription, your rules. Dedicated engineering support for regulated industries with custom model optimization and compliance documentation.",
    cta: "Talk to an Engineer",
    ctaHref: "/waitlist",
    highlighted: false,
    features: [
      "Everything in Managed",
      "Deploy into your own Azure subscription",
      "Dedicated solutions engineer",
      "Custom model optimization & tuning",
      "HIPAA / SOC 2 compliance documentation",
      "Air-gapped / sovereign cloud deployment",
      "Compound AI pipeline support",
      "Slack + phone support (1hr SLA)",
      "99.99% uptime SLA",
      "Training & fine-tuning pipeline (roadmap)",
    ],
  },
];

const faqs = [
  {
    q: "What's the difference between Pro and Managed?",
    a: "Pro gives you instant API access on our shared GPU cluster — no infrastructure to manage. Managed deploys a dedicated inference stack inside your own Azure subscription, so your data never leaves your boundary. Choose Pro to move fast, Managed when compliance requires data sovereignty.",
  },
  {
    q: "Who pays for the GPU compute?",
    a: "On Pro, compute is included in the $499/mo fee. On Managed and Enterprise, you pay Azure directly through your existing Enterprise Agreement or subscription. DirectAI never touches your compute bill — our management fee is separate.",
  },
  {
    q: "What happens if I cancel?",
    a: "On Pro, your API access stops at the end of the billing period. On Managed/Enterprise, the infrastructure keeps running in your subscription. You own the AKS cluster, the model weights, the Helm releases — everything. There is zero vendor lock-in.",
  },
  {
    q: "Can I start with Pro and upgrade later?",
    a: "Absolutely. Most customers start on Pro to validate their use case, then upgrade to Managed when they need data sovereignty or higher throughput. The API is identical — same endpoints, same SDKs.",
  },
  {
    q: "What models can I run?",
    a: "Pro tier includes curated models (Qwen, Llama, BGE, Whisper). Managed and Enterprise support any model that runs on vLLM, ONNX Runtime, or Whisper — including custom fine-tuned models.",
  },
  {
    q: "Does my data leave my Azure subscription?",
    a: "On Managed and Enterprise, never. All inference runs inside your AKS cluster on your GPU nodes. On Pro, requests go through our shared cluster — still encrypted in transit and at rest, but hosted on DirectAI infrastructure.",
  },
  {
    q: "What Azure regions do you support?",
    a: "Pro runs in East US 2 and South Central US. Managed and Enterprise deploy to any region with GPU VM availability, including sovereign and government clouds.",
  },
];

export default function PricingPage() {
  return (
    <>
      {/* Header */}
      <section className="bg-gray-950 py-20">
        <div className="mx-auto max-w-7xl px-6 text-center">
          <h1 className="text-4xl font-bold text-white sm:text-5xl">
            Start Free. Scale to Enterprise.
          </h1>
          <p className="mt-4 text-lg text-gray-400">
            Self-hosted open-source, shared API, or fully managed inference
            inside your Azure subscription — your data, your rules.
          </p>
        </div>
      </section>

      {/* Pricing Grid */}
      <section className="bg-gray-950 pb-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid gap-6 lg:grid-cols-4">
            {tiers.map((tier) => (
              <div
                key={tier.name}
                className={`relative flex flex-col rounded-xl border p-8 ${
                  tier.highlighted
                    ? "border-blue-500 bg-blue-950/20 shadow-lg shadow-blue-500/10"
                    : "border-gray-800 bg-gray-900/50"
                }`}
              >
                {tier.badge && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-600 px-3 py-1 text-xs font-semibold text-white whitespace-nowrap">
                    {tier.badge}
                  </div>
                )}
                <div>
                  <h3 className="text-lg font-semibold text-white">
                    {tier.name}
                  </h3>
                  <div className="mt-4 flex items-baseline gap-1">
                    <span className="text-4xl font-bold text-white">
                      {tier.price}
                    </span>
                    <span className="text-sm text-gray-400">
                      {tier.priceDetail}
                    </span>
                  </div>
                  <p className="mt-4 text-sm leading-6 text-gray-400">
                    {tier.description}
                  </p>
                </div>

                <ul className="mt-8 flex-1 space-y-3">
                  {tier.features.map((feature) => (
                    <li
                      key={feature}
                      className="flex items-start gap-3 text-sm"
                    >
                      <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-400" />
                      <span className="text-gray-300">{feature}</span>
                    </li>
                  ))}
                </ul>

                <div className="mt-8">
                  {tier.ctaHref.startsWith("http") ? (
                    <a
                      href={tier.ctaHref}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-center text-sm font-semibold transition ${
                        tier.highlighted
                          ? "bg-blue-600 text-white hover:bg-blue-500"
                          : "border border-gray-700 text-gray-300 hover:border-gray-600 hover:text-white"
                      }`}
                    >
                      <GitBranch className="h-4 w-4" />
                      {tier.cta}
                    </a>
                  ) : (
                    <Link
                      href={tier.ctaHref}
                      className={`block w-full rounded-lg px-4 py-2.5 text-center text-sm font-semibold transition ${
                        tier.highlighted
                          ? "bg-blue-600 text-white hover:bg-blue-500"
                          : "border border-gray-700 text-gray-300 hover:border-gray-600 hover:text-white"
                      }`}
                    >
                      {tier.cta}
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* What's Included Table */}
      <section className="border-t border-gray-800 bg-gray-950 py-24">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="text-center text-2xl font-bold text-white sm:text-3xl">
            What Azure Compute Costs Look Like
          </h2>
          <p className="mt-3 text-center text-gray-400">
            You pay Azure directly for GPU VMs through your EA. These are
            Azure&apos;s published rates — DirectAI adds zero markup on compute.
          </p>
          <div className="mt-12 overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900/50">
                  <th className="px-6 py-4 font-semibold text-white">
                    GPU SKU
                  </th>
                  <th className="px-6 py-4 font-semibold text-white">
                    Use Case
                  </th>
                  <th className="px-6 py-4 font-semibold text-white">
                    Azure Cost
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                <tr>
                  <td className="px-6 py-4 text-gray-300">
                    T4 (NC16as_T4_v3)
                  </td>
                  <td className="px-6 py-4 text-gray-300">Dev/staging, small models ≤8B</td>
                  <td className="px-6 py-4 text-gray-300">~$879/mo PAYG</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-gray-300">
                    A100 80GB (ND96asr_v4)
                  </td>
                  <td className="px-6 py-4 text-gray-300">Production LLMs (70B), transcription</td>
                  <td className="px-6 py-4 text-gray-300">~$9,947/mo 1yr RI</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-gray-300">
                    A100 PCIe (NC24ads)
                  </td>
                  <td className="px-6 py-4 text-gray-300">Embeddings, reranking, small models</td>
                  <td className="px-6 py-4 text-gray-300">~$1,654/mo 1yr RI</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-center text-xs text-gray-500">
            Prices are Azure list rates as of 2025. Your EA negotiated rates may be lower.
            Reserved Instances and Savings Plans reduce costs 40–80%.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="border-t border-gray-800 bg-gray-950 py-24">
        <div className="mx-auto max-w-3xl px-6">
          <h2 className="text-center text-2xl font-bold text-white sm:text-3xl">
            Frequently Asked Questions
          </h2>
          <div className="mt-12 space-y-8">
            {faqs.map((faq) => (
              <div key={faq.q}>
                <h3 className="text-base font-semibold text-white">{faq.q}</h3>
                <p className="mt-2 text-sm leading-6 text-gray-400">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-gray-800 bg-gray-950 py-16">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <p className="text-lg text-gray-400">
            Not sure which tier is right?{" "}
            <Link
              href="/waitlist"
              className="inline-flex items-center gap-1 font-semibold text-blue-400 transition hover:text-blue-300"
            >
              Talk to an engineer
              <ArrowRight className="h-4 w-4" />
            </Link>
          </p>
        </div>
      </section>
    </>
  );
}
