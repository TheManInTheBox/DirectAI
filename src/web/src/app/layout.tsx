import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";

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
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-background font-sans text-foreground antialiased`}
      >
        <Navbar />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
