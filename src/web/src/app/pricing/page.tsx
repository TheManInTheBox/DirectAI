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
    priceDetail: "then pay-per-use",
    description:
      "Get started instantly. Shared GPU pool with generous free tier and pay-as-you-go after.",
    cta: "Join Waitlist",
    ctaHref: "/waitlist",
    highlighted: false,
    features: [
      { text: "1,000 free requests/month", included: true },
      { text: "All modalities (LLM, embeddings, STT)", included: true },
      { text: "OpenAI-compatible API", included: true },
      { text: "Shared GPU pool", included: true },
      { text: "Community support", included: true },
      { text: "Rate limited (60 RPM)", included: true },
      { text: "Dedicated GPU allocation", included: false },
      { text: "Custom model deployment", included: false },
      { text: "SLA guarantee", included: false },
    ],
  },
  {
    name: "Pro",
    price: "$99",
    priceDetail: "/month + usage",
    description:
      "Reserved GPU capacity with burst scaling. For production workloads that need reliability.",
    cta: "Join Waitlist",
    ctaHref: "/waitlist",
    highlighted: true,
    features: [
      { text: "10,000 requests/month included", included: true },
      { text: "All modalities (LLM, embeddings, STT)", included: true },
      { text: "OpenAI-compatible API", included: true },
      { text: "Reserved GPU hours", included: true },
      { text: "Priority support (email)", included: true },
      { text: "Higher rate limits (600 RPM)", included: true },
      { text: "Burst to shared pool", included: true },
      { text: "Custom model deployment", included: false },
      { text: "99.9% SLA", included: true },
    ],
  },
  {
    name: "Enterprise",
    price: "Custom",
    priceDetail: "contact us",
    description:
      "Dedicated infrastructure in your own Azure subscription. Full isolation, custom SLAs.",
    cta: "Contact Sales",
    ctaHref: "/waitlist",
    highlighted: false,
    features: [
      { text: "Unlimited requests", included: true },
      { text: "All modalities (LLM, embeddings, STT)", included: true },
      { text: "OpenAI-compatible API", included: true },
      { text: "Dedicated GPU node pools", included: true },
      { text: "Dedicated support (Slack + phone)", included: true },
      { text: "No rate limits", included: true },
      { text: "Custom model deployment", included: true },
      { text: "Compound AI pipelines", included: true },
      { text: "99.99% SLA", included: true },
    ],
  },
  {
    name: "Self-Hosted",
    price: "$499",
    priceDetail: "/month license",
    description:
      "Run DirectAI on your own infrastructure. Full Helm chart, container images, and support.",
    cta: "Contact Sales",
    ctaHref: "/waitlist",
    highlighted: false,
    features: [
      { text: "Your infrastructure, your rules", included: true },
      { text: "All modalities (LLM, embeddings, STT)", included: true },
      { text: "OpenAI-compatible API", included: true },
      { text: "Helm chart + Docker images", included: true },
      { text: "Setup support + documentation", included: true },
      { text: "Air-gapped / sovereign deployment", included: true },
      { text: "Custom model deployment", included: true },
      { text: "Bring your own GPUs", included: true },
      { text: "Support tier add-on available", included: true },
    ],
  },
];

const faqs = [
  {
    q: "How does pay-per-use pricing work?",
    a: "After your free tier allowance, you pay per 1K tokens for LLMs, per request for embeddings and transcription. Usage is metered in real-time and billed monthly via Stripe. No surprise bills — set spend limits in your dashboard.",
  },
  {
    q: "Can I switch between tiers?",
    a: "Yes. Upgrade or downgrade anytime from your dashboard. Changes take effect at the start of your next billing cycle. Your API keys and endpoints stay the same.",
  },
  {
    q: "What models are available?",
    a: "We support Llama 3.1 (8B, 70B, 405B), Mistral, Qwen, DeepSeek for chat. BGE and E5 for embeddings. Whisper large-v3 for transcription. Enterprise and Self-Hosted tiers can deploy any custom model.",
  },
  {
    q: "What's the difference between managed and self-hosted?",
    a: "Managed tiers run on DirectAI infrastructure — we handle scaling, updates, and monitoring. Self-Hosted gives you our Helm chart and container images to run on your own Kubernetes cluster. Same engine, your servers.",
  },
  {
    q: "Do you support fine-tuned models?",
    a: "Enterprise and Self-Hosted tiers support custom model deployment. Upload your weights, and we compile optimized TensorRT-LLM engines for your target GPU. Standard architectures (Llama, Mistral, Qwen) deploy in minutes.",
  },
  {
    q: "Is there a free trial for paid tiers?",
    a: "The Developer tier is free with 1,000 requests/month — use it as your trial. If you need to evaluate Pro features, contact us for a 14-day Pro trial.",
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
            Pay-Per-Use Rates
          </h2>
          <p className="mt-3 text-center text-gray-400">
            After your tier&apos;s included allowance, usage is billed at these
            rates.
          </p>
          <div className="mt-12 overflow-hidden rounded-xl border border-gray-800">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900/50">
                  <th className="px-6 py-4 font-semibold text-white">
                    Modality
                  </th>
                  <th className="px-6 py-4 font-semibold text-white">Unit</th>
                  <th className="px-6 py-4 font-semibold text-white">
                    Developer
                  </th>
                  <th className="px-6 py-4 font-semibold text-white">Pro</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                <tr>
                  <td className="px-6 py-4 text-gray-300">
                    LLM (Chat Completions)
                  </td>
                  <td className="px-6 py-4 text-gray-400">per 1M tokens</td>
                  <td className="px-6 py-4 text-gray-300">$0.80</td>
                  <td className="px-6 py-4 text-gray-300">$0.60</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-gray-300">Embeddings</td>
                  <td className="px-6 py-4 text-gray-400">per 1M tokens</td>
                  <td className="px-6 py-4 text-gray-300">$0.05</td>
                  <td className="px-6 py-4 text-gray-300">$0.03</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-gray-300">Transcription</td>
                  <td className="px-6 py-4 text-gray-400">per hour</td>
                  <td className="px-6 py-4 text-gray-300">$0.30</td>
                  <td className="px-6 py-4 text-gray-300">$0.20</td>
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
