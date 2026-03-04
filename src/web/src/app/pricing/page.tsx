import type { Metadata } from "next";
import Link from "next/link";
import { Check, ArrowRight, Minus } from "lucide-react";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Simple, transparent pricing. From free developer tier to dedicated enterprise infrastructure.",
};

interface Tier {
  name: string;
  price: string;
  priceDetail: string;
  description: string;
  cta: string;
  ctaHref: string;
  highlighted: boolean;
  features: { text: string; included: boolean }[];
}

const tiers: Tier[] = [
  {
    name: "Developer",
    price: "Free",
    priceDetail: "$5/mo in credits",
    description:
      "Get started instantly. Shared GPU pool with generous free credits and pay-as-you-go after.",
    cta: "Join Waitlist",
    ctaHref: "/waitlist",
    highlighted: false,
    features: [
      { text: "$5/month in free credits", included: true },
      { text: "All modalities (LLM, embeddings, STT)", included: true },
      { text: "OpenAI-compatible API", included: true },
      { text: "Shared GPU pool", included: true },
      { text: "Community support", included: true },
      { text: "Rate limited (60 RPM / 100K TPM)", included: true },
      { text: "Dedicated GPU allocation", included: false },
      { text: "Custom model deployment", included: false },
      { text: "SLA guarantee", included: false },
    ],
  },
  {
    name: "Pro",
    price: "$49",
    priceDetail: "/month + usage",
    description:
      "Priority GPU access with $50/month in included credits. For production workloads that need reliability.",
    cta: "Join Waitlist",
    ctaHref: "/waitlist",
    highlighted: true,
    features: [
      { text: "$50/month in included credits", included: true },
      { text: "All modalities (LLM, embeddings, STT)", included: true },
      { text: "OpenAI-compatible API", included: true },
      { text: "Priority GPU queue", included: true },
      { text: "Email support (24hr SLA)", included: true },
      { text: "Higher rate limits (600 RPM / 1M TPM)", included: true },
      { text: "Fine-tuned model deployment", included: true },
      { text: "99.9% SLA", included: true },
      { text: "Custom model deployment", included: false },
    ],
  },
  {
    name: "Enterprise",
    price: "Custom",
    priceDetail: "contact us",
    description:
      "Dedicated infrastructure in your own Azure subscription. Full isolation, custom SLAs, and self-hosted options.",
    cta: "Contact Sales",
    ctaHref: "/waitlist",
    highlighted: false,
    features: [
      { text: "Unlimited usage", included: true },
      { text: "All modalities (LLM, embeddings, STT)", included: true },
      { text: "OpenAI-compatible API", included: true },
      { text: "Dedicated GPU node pools", included: true },
      { text: "Dedicated support (Slack + phone, 1hr SLA)", included: true },
      { text: "No rate limits", included: true },
      { text: "Custom model deployment", included: true },
      { text: "Compound AI pipelines", included: true },
      { text: "99.99% SLA + self-hosted option", included: true },
    ],
  },
];

const faqs = [
  {
    q: "How does token-based pricing work?",
    a: "Each model has its own per-token rate. LLMs charge separately for input and output tokens (output costs more because autoregressive generation is compute-intensive). Embeddings charge input tokens only. Transcription charges per minute. Usage is metered in real-time and billed monthly via Stripe.",
  },
  {
    q: "Can I switch between tiers?",
    a: "Yes. Upgrade or downgrade anytime from your dashboard. Changes take effect at the start of your next billing cycle. Your API keys and endpoints stay the same.",
  },
  {
    q: "What models are available?",
    a: "We support Llama 3.1 (8B, 70B, 405B), Mistral, Qwen, DeepSeek for chat. BGE and E5 for embeddings. Whisper large-v3 for transcription. Enterprise customers can deploy any custom model.",
  },
  {
    q: "What about self-hosted deployment?",
    a: "Self-hosted is available as an Enterprise add-on. You get our Helm chart, container images, and TensorRT-LLM engines to run on your own Kubernetes cluster — same performance, your infrastructure.",
  },
  {
    q: "Do you support fine-tuned models?",
    a: "Pro tier supports fine-tuned models with standard architectures. Enterprise tier supports fully custom model deployment. Upload your weights, and we compile optimized TensorRT-LLM engines for your target GPU.",
  },
  {
    q: "Is there a free trial?",
    a: "The Developer tier includes $5/month in free credits — enough to evaluate all modalities. If you need to evaluate Pro features, contact us for a 14-day Pro trial.",
  },
];

export default function PricingPage() {
  return (
    <>
      {/* Header */}
      <section className="bg-gray-950 py-20">
        <div className="mx-auto max-w-7xl px-6 text-center">
          <h1 className="text-4xl font-bold text-white sm:text-5xl">
            Simple, Transparent Pricing
          </h1>
          <p className="mt-4 text-lg text-gray-400">
            From free to enterprise. No hidden fees, no GPU markup games.
          </p>
        </div>
      </section>

      {/* Pricing Grid */}
      <section className="bg-gray-950 pb-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid gap-6 lg:grid-cols-3">
            {tiers.map((tier) => (
              <div
                key={tier.name}
                className={`relative flex flex-col rounded-xl border p-8 ${
                  tier.highlighted
                    ? "border-blue-500 bg-blue-950/20 shadow-lg shadow-blue-500/10"
                    : "border-gray-800 bg-gray-900/50"
                }`}
              >
                {tier.highlighted && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-600 px-3 py-1 text-xs font-semibold text-white">
                    Most Popular
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
                      key={feature.text}
                      className="flex items-start gap-3 text-sm"
                    >
                      {feature.included ? (
                        <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-400" />
                      ) : (
                        <Minus className="mt-0.5 h-4 w-4 flex-shrink-0 text-gray-600" />
                      )}
                      <span
                        className={
                          feature.included ? "text-gray-300" : "text-gray-600"
                        }
                      >
                        {feature.text}
                      </span>
                    </li>
                  ))}
                </ul>

                <div className="mt-8">
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
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Usage Pricing */}
      <section className="border-t border-gray-800 bg-gray-950 py-24">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="text-center text-2xl font-bold text-white sm:text-3xl">
            Per-Model Token Pricing
          </h2>
          <p className="mt-3 text-center text-gray-400">
            After your tier&apos;s included credits, usage is billed per
            model at these rates. Same pricing across all tiers.
          </p>
          <div className="mt-12 overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900/50">
                  <th className="px-6 py-4 font-semibold text-white">
                    Model
                  </th>
                  <th className="px-6 py-4 font-semibold text-white">
                    Input
                  </th>
                  <th className="px-6 py-4 font-semibold text-white">
                    Output
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                <tr>
                  <td className="px-6 py-4 text-gray-300">
                    Llama 3.1 8B
                  </td>
                  <td className="px-6 py-4 text-gray-300">$0.10 / 1M tokens</td>
                  <td className="px-6 py-4 text-gray-300">$0.20 / 1M tokens</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-gray-300">
                    Llama 3.1 70B
                  </td>
                  <td className="px-6 py-4 text-gray-300">$0.60 / 1M tokens</td>
                  <td className="px-6 py-4 text-gray-300">$0.80 / 1M tokens</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-gray-300">
                    Embeddings (bge-large)
                  </td>
                  <td className="px-6 py-4 text-gray-300">$0.02 / 1M tokens</td>
                  <td className="px-6 py-4 text-gray-500">—</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-gray-300">
                    Whisper large-v3
                  </td>
                  <td className="px-6 py-4 text-gray-500">—</td>
                  <td className="px-6 py-4 text-gray-300">$0.10 / minute</td>
                </tr>
              </tbody>
            </table>
          </div>
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
            Not sure which plan is right?{" "}
            <Link
              href="/waitlist"
              className="inline-flex items-center gap-1 font-semibold text-blue-400 transition hover:text-blue-300"
            >
              Talk to us
              <ArrowRight className="h-4 w-4" />
            </Link>
          </p>
        </div>
      </section>
    </>
  );
}
