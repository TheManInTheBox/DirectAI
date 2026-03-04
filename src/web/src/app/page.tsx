import Link from "next/link";
import {
  Zap,
  Shield,
  Globe,
  Cpu,
  ArrowRight,
  Terminal,
  BarChart3,
  Layers,
} from "lucide-react";

const features = [
  {
    icon: Zap,
    title: "Sub-100ms Latency",
    description:
      "TensorRT-LLM compiled engines, NVMe-cached weights, and GPU-optimized scheduling deliver inference that's faster than the competition.",
  },
  {
    icon: Layers,
    title: "Every Modality",
    description:
      "LLMs, embeddings, transcription, reranking — one platform, one API. OpenAI-compatible, zero code changes.",
  },
  {
    icon: Terminal,
    title: "OpenAI Drop-In",
    description:
      "Point your existing SDK at DirectAI. Same /v1/chat/completions, /v1/embeddings, /v1/audio/transcriptions endpoints.",
  },
  {
    icon: BarChart3,
    title: "Autoscaling to Zero",
    description:
      "Pay nothing when idle. KEDA-driven pod scaling with cluster autoscaler drains GPU nodes for true zero-cost idle.",
  },
  {
    icon: Shield,
    title: "Enterprise Security",
    description:
      "Per-customer subscription isolation, RBAC, TLS 1.2+, Key Vault secrets, SOC 2 and HIPAA-ready architecture.",
  },
  {
    icon: Globe,
    title: "Multi-Cloud Ready",
    description:
      "Azure-first with clean provider interfaces. Deploy on GCP or AWS with a config change, not a rewrite.",
  },
];

const codeExample = `curl https://api.agilecloud.ai/v1/chat/completions \\
  -H "Authorization: Bearer $DIRECTAI_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "llama-3.1-70b-instruct",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'`;

const stats = [
  { value: "<100ms", label: "P99 Latency" },
  { value: "99.99%", label: "Uptime Target" },
  { value: "$0", label: "Idle Cost" },
  { value: "∞", label: "Scale Ceiling" },
];

export default function HomePage() {
  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-950 via-gray-950 to-black" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(59,130,246,0.15),transparent_50%)]" />
        <div className="relative mx-auto max-w-7xl px-6 py-24 sm:py-32 lg:py-40">
          <div className="mx-auto max-w-3xl text-center">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-1.5 text-sm text-blue-300">
              <Cpu className="h-4 w-4" />
              Now in Early Access
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl lg:text-7xl">
              AI Inference{" "}
              <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                Without Limits
              </span>
            </h1>
            <p className="mt-6 text-lg leading-8 text-gray-300 sm:text-xl">
              Deploy any model — LLMs, embeddings, transcription — with
              production-grade latency, autoscaling to zero, and OpenAI API
              compatibility. No rewrite required.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/waitlist"
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-blue-500"
              >
                Join the Waitlist
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/pricing"
                className="inline-flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-900/50 px-6 py-3 text-sm font-semibold text-gray-300 transition hover:border-gray-600 hover:text-white"
              >
                View Pricing
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Bar */}
      <section className="border-y border-gray-800 bg-gray-950/50">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-8 px-6 py-12 sm:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="text-3xl font-bold text-white sm:text-4xl">
                {stat.value}
              </div>
              <div className="mt-1 text-sm text-gray-400">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features Grid */}
      <section className="bg-gray-950 py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Built for Production
            </h2>
            <p className="mt-4 text-lg text-gray-400">
              Not another demo platform. DirectAI is engineered for
              enterprise-grade workloads from day one.
            </p>
          </div>
          <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="group rounded-xl border border-gray-800 bg-gray-900/50 p-8 transition hover:border-gray-700 hover:bg-gray-900"
              >
                <div className="mb-4 inline-flex rounded-lg bg-blue-500/10 p-3 text-blue-400 transition group-hover:bg-blue-500/20">
                  <feature.icon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-white">
                  {feature.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-gray-400">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Code Example */}
      <section className="border-t border-gray-800 bg-gray-950 py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div>
              <h2 className="text-3xl font-bold text-white sm:text-4xl">
                One Line to Switch
              </h2>
              <p className="mt-4 text-lg text-gray-400">
                Already using the OpenAI SDK? Change the base URL. That&apos;s
                it. Same endpoints, same request format, same streaming — just
                faster and cheaper.
              </p>
              <ul className="mt-8 space-y-3 text-gray-300">
                {[
                  "/v1/chat/completions — LLMs with streaming SSE",
                  "/v1/embeddings — Text embeddings at batch scale",
                  "/v1/audio/transcriptions — Whisper STT",
                  "/v1/models — List all deployed models",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm">
                    <div className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-500" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div className="overflow-hidden rounded-xl border border-gray-800 bg-black">
              <div className="flex items-center gap-2 border-b border-gray-800 px-4 py-3">
                <div className="h-3 w-3 rounded-full bg-red-500/50" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/50" />
                <div className="h-3 w-3 rounded-full bg-green-500/50" />
                <span className="ml-2 text-xs text-gray-500">terminal</span>
              </div>
              <pre className="overflow-x-auto p-6 text-sm leading-relaxed text-green-400">
                <code>{codeExample}</code>
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-gray-800 bg-gray-950 py-24">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-bold text-white sm:text-4xl">
            Ready to Ship Faster?
          </h2>
          <p className="mt-4 text-lg text-gray-400">
            Join the waitlist for early access. Be first in line when we open
            the gates.
          </p>
          <div className="mt-8">
            <Link
              href="/waitlist"
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-8 py-3.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-blue-500"
            >
              Join the Waitlist
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
