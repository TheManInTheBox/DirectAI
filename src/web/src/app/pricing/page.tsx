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
    priceDetail: "$5 credit on shared API",
    description:
      "Self-host with our open-source Helm charts and Bicep templates — or try the shared API with $5 of free credit. No credit card required.",
    cta: "View on GitHub",
    ctaHref: "https://github.com/TheManInTheBox/DirectAI",
    highlighted: false,
    features: [
      "Full Helm chart & Bicep templates",
      "vLLM, ONNX Runtime, Whisper engines",
      "OpenAI-compatible API server",
      "GPU autoscaling (KEDA + Cluster Autoscaler)",
      "$5 one-time API credit (shared cluster)",
      "20 RPM / 40K TPM rate limits",
      "Community support (GitHub Issues)",
      "Apache 2.0 license",
    ],
  },
  {
    name: "Pro",
    price: "$50",
    priceDetail: "/month + usage",
    description:
      "Instant access to our shared GPU cluster. Pay a low base fee plus per-token usage. OpenAI-compatible API — start building in minutes.",
    cta: "Get Started",
    ctaHref: "/waitlist",
    highlighted: true,
    badge: "Best for Developers",
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
  {
    name: "Managed",
    price: "$3,500",
    priceDetail: "/month + usage",
    description:
      "DirectAI deploys and manages inference inside a dedicated Azure subscription we own on your behalf. Base fee covers operations — usage billed per token.",
    cta: "Talk to an Engineer",
    ctaHref: "/waitlist",
    highlighted: false,
    features: [
      "Everything in Pro",
      "Dedicated Azure subscription",
      "Isolated infrastructure & networking",
      "Entra ID & Private Link integration",
      "Azure Monitor dashboards & alerts",
      "Scaling configuration & optimization",
      "Model updates & security patches",
      "Email support (24hr SLA)",
      "1,000 RPM / 5M TPM rate limits",
      "99.9% uptime SLA",
    ],
  },
  {
    name: "Enterprise",
    price: "Custom",
    priceDetail: "starting at $10K/month",
    description:
      "Your Azure subscription, your rules. Flat management fee — no per-token metering. Dedicated engineering support for regulated industries.",
    cta: "Talk to an Engineer",
    ctaHref: "/waitlist",
    highlighted: false,
    features: [
      "Everything in Managed",
      "Deploy into your own Azure subscription",
      "Flat fee — no usage metering",
      "Dedicated solutions engineer",
      "Custom model optimization & tuning",
      "HIPAA / SOC 2 compliance documentation",
      "Air-gapped / sovereign cloud deployment",
      "Compound AI pipeline support",
      "Slack + phone support (1hr SLA)",
      "99.99% uptime SLA",
    ],
  },
];

const faqs = [
  {
    q: "What's the difference between Pro and Managed?",
    a: "Pro gives you instant API access on our shared GPU cluster — $50/mo base plus per-token usage. Managed deploys a dedicated inference stack in an Azure subscription we own on your behalf, so your data is fully isolated. Choose Pro to move fast, Managed when you need dedicated infrastructure and higher throughput.",
  },
  {
    q: "How does usage billing work?",
    a: "Pro and Managed charge per token processed. Chat completions: $1.00 per million input tokens, $2.00 per million output tokens (Pro rates). Embeddings: $0.10 per million tokens. Transcription: $0.10 per minute. Managed rates are 2× Pro. Enterprise pays a flat management fee with no per-token metering.",
  },
  {
    q: "Who pays for the GPU compute?",
    a: "On Free and Pro, compute is included — you just pay the base fee plus usage. On Managed, DirectAI owns the Azure subscription and compute costs are baked into the per-token rates. On Enterprise, you pay Azure directly through your EA — DirectAI charges a flat management fee.",
  },
  {
    q: "What happens if I cancel?",
    a: "On Pro, your API access stops at the end of the billing period. On Managed, we decommission the dedicated infrastructure. On Enterprise, the infrastructure keeps running in your subscription — you own the AKS cluster, the model weights, the Helm releases. Zero vendor lock-in.",
  },
  {
    q: "Can I start with Pro and upgrade later?",
    a: "Absolutely. Most customers start on Pro to validate their use case, then upgrade to Managed when they need isolated infrastructure or higher throughput. The API is identical — same endpoints, same SDKs.",
  },
  {
    q: "What models can I run?",
    a: "Free (self-hosted) supports any model that runs on vLLM, ONNX Runtime, or Whisper. Pro includes curated models (Qwen, Llama, BGE, Whisper). Managed and Enterprise support any model including custom fine-tuned weights.",
  },
  {
    q: "What about the $5 free credit?",
    a: "Sign up for a Free account and get $5 of API credit on our shared cluster — no credit card needed. Use it to test chat completions, embeddings, or transcription. When the credit runs out, upgrade to Pro for continued access.",
  },
  {
    q: "What Azure regions do you support?",
    a: "Pro runs in East US 2 and South Central US. Managed deploys to any region with GPU VM availability. Enterprise supports sovereign and government clouds.",
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

      {/* Per-Token Pricing Table */}
      <section className="border-t border-gray-800 bg-gray-950 py-24">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="text-center text-2xl font-bold text-white sm:text-3xl">
            Per-Token Usage Rates
          </h2>
          <p className="mt-3 text-center text-gray-400">
            Pro and Managed tiers pay per token processed. Enterprise pays a
            flat management fee with no per-token metering.
          </p>
          <div className="mt-12 overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900/50">
                  <th className="px-6 py-4 font-semibold text-white">
                    Modality
                  </th>
                  <th className="px-6 py-4 font-semibold text-white">
                    Metric
                  </th>
                  <th className="px-6 py-4 font-semibold text-white">
                    Pro Rate
                  </th>
                  <th className="px-6 py-4 font-semibold text-white">
                    Managed Rate
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                <tr>
                  <td className="px-6 py-4 text-gray-300">Chat — input</td>
                  <td className="px-6 py-4 text-gray-300">per 1M tokens</td>
                  <td className="px-6 py-4 text-gray-300">$1.00</td>
                  <td className="px-6 py-4 text-gray-300">$2.00</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-gray-300">Chat — output</td>
                  <td className="px-6 py-4 text-gray-300">per 1M tokens</td>
                  <td className="px-6 py-4 text-gray-300">$2.00</td>
                  <td className="px-6 py-4 text-gray-300">$4.00</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-gray-300">Embeddings</td>
                  <td className="px-6 py-4 text-gray-300">per 1M tokens</td>
                  <td className="px-6 py-4 text-gray-300">$0.10</td>
                  <td className="px-6 py-4 text-gray-300">$0.20</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-gray-300">Transcription</td>
                  <td className="px-6 py-4 text-gray-300">per minute</td>
                  <td className="px-6 py-4 text-gray-300">$0.10</td>
                  <td className="px-6 py-4 text-gray-300">$0.20</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-center text-xs text-gray-500">
            Free tier gets a one-time $5 credit at Pro rates. Enterprise pricing
            is a flat monthly fee — contact us for a quote.
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
