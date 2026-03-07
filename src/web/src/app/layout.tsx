import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { ConditionalFooter } from "@/components/conditional-footer";
import { SessionProvider } from "@/components/session-provider";
import { AppInsightsProvider } from "@/components/app-insights-provider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "DirectAI — AI Inference Inside Your Azure",
    template: "%s | DirectAI",
  },
  description:
    "Production-grade AI inference that deploys inside your Azure subscription. HIPAA-ready, Entra ID integrated, open source. Your data never leaves your boundary.",
  keywords: [
    "Azure AI inference",
    "LLM deployment Azure",
    "HIPAA AI inference",
    "AKS GPU inference",
    "vLLM Azure",
    "OpenAI compatible API",
    "enterprise AI infrastructure",
    "self-hosted inference",
    "Azure Kubernetes GPU",
    "regulated AI deployment",
  ],
  openGraph: {
    title: "DirectAI — AI Inference Inside Your Azure",
    description:
      "Production-grade AI inference that deploys inside your Azure subscription. HIPAA-ready, open source, zero vendor lock-in.",
    url: "https://agilecloud.ai",
    siteName: "DirectAI",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "DirectAI — AI Inference Inside Your Azure",
    description:
      "Production-grade AI inference that deploys inside your Azure subscription. HIPAA-ready, open source, zero vendor lock-in.",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <Script id="linkedin-partner" strategy="afterInteractive">{`
          _linkedin_partner_id = "8912820";
          window._linkedin_data_partner_ids = window._linkedin_data_partner_ids || [];
          window._linkedin_data_partner_ids.push(_linkedin_partner_id);
        `}</Script>
        <Script id="linkedin-insight" strategy="afterInteractive">{`
          (function(l) {
            if (!l){window.lintrk = function(a,b){window.lintrk.q.push([a,b])};
            window.lintrk.q=[]}
            var s = document.getElementsByTagName("script")[0];
            var b = document.createElement("script");
            b.type = "text/javascript";b.async = true;
            b.src = "https://snap.licdn.com/li.lms-analytics/insight.min.js";
            s.parentNode.insertBefore(b, s);
          })(window.lintrk);
        `}</Script>
        <noscript>
          <img
            height="1"
            width="1"
            style={{ display: "none" }}
            alt=""
            src="https://px.ads.linkedin.com/collect/?pid=8912820&fmt=gif"
          />
        </noscript>
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-background font-sans text-foreground antialiased`}
      >
        <SessionProvider>
          <AppInsightsProvider>
            <Navbar />
            <main>{children}</main>
            <ConditionalFooter />
          </AppInsightsProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
