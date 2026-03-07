import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",

  // OTEL / Azure Monitor packages use native modules that can't be bundled
  serverExternalPackages: [
    "@azure/monitor-opentelemetry",
    "@opentelemetry/api",
    "@opentelemetry/sdk-node",
    "@opentelemetry/sdk-trace-node",
    "@opentelemetry/exporter-trace-otlp-http",
    "@azure/monitor-opentelemetry-exporter",
  ],
};

export default nextConfig;
