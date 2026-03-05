import Link from "next/link";
import {
  Shield,
  Globe,
  ArrowRight,
  Terminal,
  Server,
  Lock,
  Building2,
  HeartPulse,
  Landmark,
  GitBranch,
  MonitorCheck,
  KeyRound,
  CloudCog,
} from "lucide-react";

const capabilities = [
  {
    icon: Server,
    title: "Runs in Your Subscription",
    description:
      "Inference deploys inside your Azure subscription. Your VNet, your node pools, your EA credits. Data never leaves your boundary.",
  },
  {
    icon: Lock,
    title: "Data Sovereignty by Default",
    description:
      "Private Link, Azure CNI, network policy enforcement. No traffic traverses the public internet. Your compliance perimeter stays intact.",
  },
  {
    icon: Terminal,
    title: "OpenAI-Compatible API",
    description:
      "Same /v1/chat/completions, /v1/embeddings, /v1/audio/transcriptions. Point your existing SDK at your own endpoint. Zero code changes.",
  },
  {
    icon: MonitorCheck,
    title: "Azure Monitor Native",
    description:
      "Metrics, logs, and traces flow to your existing Azure Monitor and Application Insights. No third-party observability vendor required.",
  },
  {
    icon: KeyRound,
    title: "Entra ID Integrated",
    description:
      "Workload identity for pods, Entra RBAC for clusters, Key Vault for secrets. Fits your existing identity and access management.",
  },
  {
    icon: CloudCog,
    title: "Autoscaling to Zero",
    description:
      "KEDA-driven pod scaling with Cluster Autoscaler. GPU nodes drain when idle — true zero-cost when nothing is running. Pay only for what you use.",
  },
];

const verticals = [
  {
    icon: HeartPulse,
    name: "Healthcare",
    description:
      "HIPAA-ready inference for clinical transcription, medical summarization, and clinical search. Whisper + Llama + embeddings in your Azure boundary.",
  },
  {
    icon: Landmark,
    name: "Financial Services",
    description:
      "Run LLMs for document processing, compliance analysis, and customer interactions on dedicated GPU nodes within your regulated Azure environment.",
  },
  {
    icon: Building2,
    name: "Government & Public Sector",
    description:
      "Deploy open-source models on Azure Government or sovereign cloud regions. Air-gapped option with no external dependencies.",
  },
];

const codeExample = `# Deploy to your Azure subscription with Helm
helm install directai oci://agilecloud.ai/charts/directai \\
  --namespace directai --create-namespace \\
  --values values-prod.yaml

# Inference runs inside your AKS cluster
curl https://inference.internal.yourcompany.com/v1/chat/completions \\
  -H "Authorization: Bearer $YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "llama-3.1-70b-instruct",
    "messages": [{"role": "user", "content": "Summarize this clinical note."}],
    "stream": true
  }'`;

const trustSignals = [
  { value: "0", label: "Data leaves your Azure boundary" },
  { value: "100%", label: "Open-source stack" },
  { value: "Your EA", label: "Credits pay for compute" },
  { value: "99.99%", label: "Uptime target" },
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
              <Shield className="h-4 w-4" />
              Azure-Native · HIPAA-Ready · Open Source
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl lg:text-7xl">
              AI Inference{" "}
              <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                Inside Your
              </span>{" "}
              Azure
            </h1>
            <p className="mt-6 text-lg leading-8 text-gray-300 sm:text-xl">
              Production-grade LLM, embedding, and transcription inference that
              deploys into your Azure subscription. Your data never leaves. Your
              EA credits pay for compute. Your compliance perimeter stays intact.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/waitlist"
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-blue-500"
              >
                Talk to an Engineer
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="https://github.com/TheManInTheBox/DirectAI"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-900/50 px-6 py-3 text-sm font-semibold text-gray-300 transition hover:border-gray-600 hover:text-white"
              >
                <GitBranch className="h-4 w-4" />
                View on GitHub
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Trust Signals Bar */}
      <section className="border-y border-gray-800 bg-gray-950/50">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-8 px-6 py-12 sm:grid-cols-4">
          {trustSignals.map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="text-3xl font-bold text-white sm:text-4xl">
                {stat.value}
              </div>
              <div className="mt-1 text-sm text-gray-400">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Problem Statement */}
      <section className="bg-gray-950 py-24">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-bold text-white sm:text-4xl">
            The Problem
          </h2>
          <p className="mt-6 text-lg leading-8 text-gray-400">
            Your team wants to run open-source AI models in production. But
            third-party inference APIs send your data outside your Azure
            boundary. Azure ML managed endpoints are slow and expensive.
            And setting up vLLM on AKS with GPU autoscaling, TLS, monitoring,
            and RBAC is a 6-month platform engineering project.
          </p>
          <p className="mt-4 text-lg font-medium text-blue-400">
            DirectAI closes that gap in days, not months.
          </p>
        </div>
      </section>

      {/* Capabilities Grid */}
      <section className="border-t border-gray-800 bg-gray-950 py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Built for Regulated Azure Environments
            </h2>
            <p className="mt-4 text-lg text-gray-400">
              Not a multi-cloud API service. A deployment stack purpose-built
              for Azure-first enterprises with real compliance requirements.
            </p>
          </div>
          <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {capabilities.map((cap) => (
              <div
                key={cap.title}
                className="group rounded-xl border border-gray-800 bg-gray-900/50 p-8 transition hover:border-gray-700 hover:bg-gray-900"
              >
                <div className="mb-4 inline-flex rounded-lg bg-blue-500/10 p-3 text-blue-400 transition group-hover:bg-blue-500/20">
                  <cap.icon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-white">
                  {cap.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-gray-400">
                  {cap.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Industry Verticals */}
      <section className="border-t border-gray-800 bg-gray-950 py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Purpose-Built for Regulated Industries
            </h2>
            <p className="mt-4 text-lg text-gray-400">
              When your data can&apos;t leave your Azure subscription, third-party
              inference APIs aren&apos;t an option. DirectAI is.
            </p>
          </div>
          <div className="mt-16 grid gap-8 lg:grid-cols-3">
            {verticals.map((v) => (
              <div
                key={v.name}
                className="rounded-xl border border-gray-800 bg-gray-900/50 p-8 transition hover:border-gray-700"
              >
                <div className="mb-4 inline-flex rounded-lg bg-blue-500/10 p-3 text-blue-400">
                  <v.icon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-white">{v.name}</h3>
                <p className="mt-2 text-sm leading-6 text-gray-400">
                  {v.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Code / Deploy Example */}
      <section className="border-t border-gray-800 bg-gray-950 py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div>
              <h2 className="text-3xl font-bold text-white sm:text-4xl">
                Deploy in Your Cluster,{" "}
                <span className="text-blue-400">Not Ours</span>
              </h2>
              <p className="mt-4 text-lg text-gray-400">
                DirectAI ships as Helm charts and Bicep templates. It deploys
                into your existing AKS cluster, uses your Entra ID, and serves
                inference on your GPU node pools. You own the entire stack.
              </p>
              <ul className="mt-8 space-y-3 text-gray-300">
                {[
                  "Helm chart → your AKS namespace",
                  "Bicep templates → your Azure subscription",
                  "Model weights → your Azure Blob Storage",
                  "Secrets → your Azure Key Vault",
                  "Metrics → your Azure Monitor",
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

      {/* How It Works */}
      <section className="border-t border-gray-800 bg-gray-950 py-24">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="text-center text-3xl font-bold text-white sm:text-4xl">
            How It Works
          </h2>
          <div className="mt-16 space-y-12">
            {[
              {
                step: "01",
                title: "We deploy into your Azure subscription",
                description:
                  "Bicep templates provision AKS with GPU node pools, VNet, Key Vault, and managed identities. Everything in your subscription, governed by your Azure Policy.",
              },
              {
                step: "02",
                title: "Models deploy to your cluster",
                description:
                  "Helm charts spin up inference backends — vLLM for LLMs, ONNX Runtime for embeddings, Whisper for transcription. Weights stored in your Blob Storage, served from your GPU pods.",
              },
              {
                step: "03",
                title: "Your team hits an internal API",
                description:
                  "OpenAI-compatible endpoints on your Private Link or internal load balancer. Existing SDKs work unchanged. Autoscaling handles spikes. You see everything in Azure Monitor.",
              },
              {
                step: "04",
                title: "We manage, you own",
                description:
                  "DirectAI handles updates, scaling config, model optimization, and incident response. You own the infrastructure, the data, and the compliance posture. Cancel anytime — the stack keeps running.",
              },
            ].map((item) => (
              <div key={item.step} className="flex gap-6">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
                  {item.step}
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-gray-400">
                    {item.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-gray-800 bg-gray-950 py-24">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <Globe className="mx-auto h-12 w-12 text-blue-400" />
          <h2 className="mt-6 text-3xl font-bold text-white sm:text-4xl">
            Ready to Run AI on Your Terms?
          </h2>
          <p className="mt-4 text-lg text-gray-400">
            Talk to an engineer about deploying production-grade inference
            inside your Azure subscription. No commitment, no vendor lock-in.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href="/waitlist"
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-8 py-3.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-blue-500"
            >
              Talk to an Engineer
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/pricing"
              className="inline-flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-900/50 px-8 py-3.5 text-sm font-semibold text-gray-300 transition hover:border-gray-600 hover:text-white"
            >
              View Pricing
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
