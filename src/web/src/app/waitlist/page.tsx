import type { Metadata } from "next";
import { WaitlistForm } from "./waitlist-form";
import { Shield, Clock, Wrench } from "lucide-react";

export const metadata: Metadata = {
  title: "Talk to an Engineer — DirectAI",
  description:
    "Schedule a technical walkthrough of DirectAI. We'll map your compliance requirements, workloads, and Azure environment to a deployment plan.",
};

const outcomes = [
  {
    icon: Shield,
    title: "Compliance mapping",
    description:
      "We'll audit your HIPAA, SOC 2, or data residency requirements and show exactly how DirectAI satisfies them inside your Azure boundary.",
  },
  {
    icon: Wrench,
    title: "Architecture review",
    description:
      "Walk through your current inference workloads — models, traffic patterns, GPU requirements — and get a production deployment plan.",
  },
  {
    icon: Clock,
    title: "Live deployment estimate",
    description:
      "Get a concrete timeline and Azure cost estimate for your workloads. Most managed deployments go live in under 2 weeks.",
  },
];

export default function WaitlistPage() {
  return (
    <section className="bg-gray-950 py-24">
      <div className="mx-auto max-w-5xl px-6">
        <div className="grid gap-16 lg:grid-cols-2">
          {/* Left: messaging */}
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-1.5 text-sm text-blue-300">
              No sales pitch — just engineers
            </div>
            <h1 className="text-4xl font-bold text-white sm:text-5xl">
              Talk to an Engineer
            </h1>
            <p className="mt-4 text-lg text-gray-400">
              Tell us about your workloads and compliance requirements.
              We&apos;ll respond within one business day with a technical
              assessment — not a sales deck.
            </p>

            <div className="mt-12 space-y-8">
              {outcomes.map((item) => (
                <div key={item.title} className="flex gap-4">
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-gray-800">
                    <item.icon className="h-5 w-5 text-blue-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white">{item.title}</h3>
                    <p className="mt-1 text-sm text-gray-400">
                      {item.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: form */}
          <div className="flex items-start justify-center lg:pt-12">
            <WaitlistForm />
          </div>
        </div>
      </div>
    </section>
  );
}
