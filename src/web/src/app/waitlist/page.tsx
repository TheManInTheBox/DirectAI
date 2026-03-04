import type { Metadata } from "next";
import { WaitlistForm } from "./waitlist-form";
import { Sparkles } from "lucide-react";

export const metadata: Metadata = {
  title: "Waitlist",
  description:
    "Join the DirectAI waitlist for early access to production-grade AI inference.",
};

const perks = [
  "Early access to the platform before public launch",
  "Free Developer tier with 1,000 requests/month",
  "Direct line to the engineering team",
  "Priority access to new models and features",
];

export default function WaitlistPage() {
  return (
    <section className="bg-gray-950 py-24">
      <div className="mx-auto max-w-3xl px-6 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-1.5 text-sm text-blue-300">
          <Sparkles className="h-4 w-4" />
          Limited Early Access
        </div>
        <h1 className="text-4xl font-bold text-white sm:text-5xl">
          Get Early Access
        </h1>
        <p className="mt-4 text-lg text-gray-400">
          We&apos;re onboarding teams in batches. Drop your email and we&apos;ll
          reach out when it&apos;s your turn.
        </p>

        <div className="mt-12">
          <WaitlistForm />
        </div>

        <div className="mt-16">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500">
            What you get
          </h2>
          <ul className="mt-6 space-y-3">
            {perks.map((perk) => (
              <li
                key={perk}
                className="flex items-center justify-center gap-3 text-sm text-gray-300"
              >
                <div className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-500" />
                {perk}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
