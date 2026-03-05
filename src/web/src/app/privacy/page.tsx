import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy — DirectAI",
  description: "DirectAI Privacy Policy — how we collect, use, and protect your data.",
};

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-20 text-zinc-300">
      <h1 className="text-3xl font-bold text-white mb-2">Privacy Policy</h1>
      <p className="text-sm text-zinc-500 mb-10">
        Last updated: March 4, 2026
      </p>

      <div className="space-y-8 text-sm leading-relaxed">
        <section>
          <h2 className="text-lg font-semibold text-white mb-2">1. Introduction</h2>
          <p>
            Agile Cloud LLC (&quot;DirectAI,&quot; &quot;we,&quot; &quot;us&quot;) operates the DirectAI inference
            API platform at agilecloud.ai. This Privacy Policy describes how we collect, use,
            disclose, and protect your information when you use our Service.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-2">2. Information We Collect</h2>

          <h3 className="text-sm font-semibold text-zinc-200 mt-4 mb-1">Account Information</h3>
          <p>
            When you create an account, we collect your name, email address, and authentication
            provider details (Microsoft, Google, GitHub, or email). This is processed through
            Microsoft Entra External ID and stored in our PostgreSQL database.
          </p>

          <h3 className="text-sm font-semibold text-zinc-200 mt-4 mb-1">Payment Information</h3>
          <p>
            Payment details (credit card, billing address) are collected and processed by Stripe.
            We do not store your full payment information — only a Stripe customer reference ID.
          </p>

          <h3 className="text-sm font-semibold text-zinc-200 mt-4 mb-1">API Usage Data</h3>
          <p>
            We log metadata about your API requests: model name, token counts (input/output),
            request timestamp, modality, and correlation IDs. This data is used for billing,
            rate limiting, and abuse prevention.
          </p>

          <h3 className="text-sm font-semibold text-zinc-200 mt-4 mb-1">API Request Content</h3>
          <p>
            Your API inputs (prompts, text, audio files) are processed transiently to generate
            inference responses. <strong className="text-white">We do not store, log, or use your
            API input/output content for any purpose other than delivering the response.</strong>{" "}
            Content is not used to train or improve models.
          </p>

          <h3 className="text-sm font-semibold text-zinc-200 mt-4 mb-1">Technical Data</h3>
          <p>
            We collect standard web analytics: IP address, browser type, device information,
            and pages visited on agilecloud.ai. Server logs include request timing, status codes,
            and correlation IDs for operational monitoring.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-2">3. How We Use Your Information</h2>
          <ul className="list-disc list-inside space-y-1 text-zinc-400">
            <li>Provide, maintain, and improve the Service</li>
            <li>Process payments and calculate usage-based billing</li>
            <li>Send account-related communications (billing, security alerts, service updates)</li>
            <li>Enforce our Terms of Service and prevent abuse</li>
            <li>Comply with legal obligations</li>
            <li>Respond to your support requests</li>
          </ul>
          <p className="mt-2">
            We do <strong className="text-white">not</strong> sell your personal information
            or use your API content to train machine learning models.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-2">4. Data Retention</h2>
          <ul className="list-disc list-inside space-y-1 text-zinc-400">
            <li><strong className="text-zinc-200">Account data:</strong> Retained while your account is active. Deleted within 30 days of account closure.</li>
            <li><strong className="text-zinc-200">Usage records:</strong> Retained for 90 days for billing, then aggregated and anonymized.</li>
            <li><strong className="text-zinc-200">API content:</strong> Not retained. Processed transiently in memory only.</li>
            <li><strong className="text-zinc-200">Server logs:</strong> Retained for 30 days for operational monitoring.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-2">5. Data Sharing</h2>
          <p>We share your information only with:</p>
          <ul className="list-disc list-inside mt-2 space-y-1 text-zinc-400">
            <li><strong className="text-zinc-200">Stripe</strong> — payment processing</li>
            <li><strong className="text-zinc-200">Microsoft Azure</strong> — cloud infrastructure (data processed within your deployment region)</li>
            <li><strong className="text-zinc-200">Microsoft Entra</strong> — identity authentication</li>
          </ul>
          <p className="mt-2">
            We do not share your data with third parties for marketing or advertising purposes.
            We may disclose information if required by law or to protect our rights.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-2">6. Security</h2>
          <p>
            We implement industry-standard security measures including:
          </p>
          <ul className="list-disc list-inside mt-2 space-y-1 text-zinc-400">
            <li>TLS 1.2+ encryption for all data in transit</li>
            <li>Encryption at rest for all stored data (Azure-managed keys)</li>
            <li>API keys stored as irreversible SHA-256 hashes</li>
            <li>Role-based access control with principle of least privilege</li>
            <li>Network isolation via Azure Virtual Networks</li>
            <li>Regular security assessments and monitoring</li>
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-2">7. Your Rights</h2>
          <p>Depending on your jurisdiction, you may have the right to:</p>
          <ul className="list-disc list-inside mt-2 space-y-1 text-zinc-400">
            <li>Access the personal data we hold about you</li>
            <li>Request correction of inaccurate data</li>
            <li>Request deletion of your data</li>
            <li>Object to or restrict processing</li>
            <li>Data portability</li>
          </ul>
          <p className="mt-2">
            To exercise these rights, contact us at{" "}
            <a href="mailto:privacy@agilecloud.ai" className="text-blue-400 hover:underline">
              privacy@agilecloud.ai
            </a>
            .
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-2">8. International Transfers</h2>
          <p>
            Your data may be processed in the United States or other regions where our cloud
            infrastructure operates. We use Azure regions to keep data in your selected deployment
            region where possible. Enterprise customers can specify data residency requirements.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-2">9. Children</h2>
          <p>
            The Service is not directed to individuals under 18. We do not knowingly collect
            information from children. If we discover we have collected such information, we
            will delete it promptly.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-2">10. Changes to This Policy</h2>
          <p>
            We may update this Privacy Policy periodically. We will notify you of material
            changes via email or a prominent notice on the Service. Your continued use after
            changes constitutes acceptance.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-2">11. Contact</h2>
          <p>
            Questions about this Privacy Policy? Contact us at{" "}
            <a href="mailto:privacy@agilecloud.ai" className="text-blue-400 hover:underline">
              privacy@agilecloud.ai
            </a>
            .
          </p>
          <div className="mt-4 text-zinc-500">
            <p>Agile Cloud LLC</p>
            <p>Austin, TX</p>
          </div>
        </section>
      </div>

      <div className="mt-12 pt-8 border-t border-zinc-800 text-sm text-zinc-500">
        See also:{" "}
        <Link href="/terms" className="text-blue-400 hover:underline">
          Terms of Service
        </Link>
      </div>
    </main>
  );
}
