import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { ConditionalFooter } from "@/components/conditional-footer";
import { SessionProvider } from "@/components/session-provider";

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
    default: "DirectAI — AI Inference Without Limits",
    template: "%s | DirectAI",
  },
  description:
    "Deploy any AI model with production-grade latency, autoscaling to zero, and OpenAI API compatibility. LLMs, embeddings, transcription — one platform.",
  keywords: [
    "AI inference",
    "LLM API",
    "embeddings",
    "transcription",
    "OpenAI compatible",
    "GPU autoscaling",
    "TensorRT-LLM",
    "model deployment",
  ],
  openGraph: {
    title: "DirectAI — AI Inference Without Limits",
    description:
      "Deploy any AI model with production-grade latency, autoscaling to zero, and OpenAI API compatibility.",
    url: "https://agilecloud.ai",
    siteName: "DirectAI",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "DirectAI — AI Inference Without Limits",
    description:
      "Deploy any AI model with production-grade latency, autoscaling to zero, and OpenAI API compatibility.",
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
          <Navbar />
          <main>{children}</main>
          <ConditionalFooter />
        </SessionProvider>
      </body>
    </html>
  );
}
