/**
 * Next.js Instrumentation — Server-Side Azure Monitor OpenTelemetry
 *
 * Runs once on server startup. Sends traces, dependencies, exceptions, and
 * request telemetry to Application Insights for all server-side Next.js
 * rendering (RSC, API routes, middleware).
 *
 * Requires APPLICATIONINSIGHTS_CONNECTION_STRING env var.
 *
 * @see https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 */

export async function register() {
  // Only instrument the Node.js runtime (not Edge)
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const connectionString =
      process.env.APPLICATIONINSIGHTS_CONNECTION_STRING;

    if (!connectionString) {
      console.warn(
        "[DirectAI] APPLICATIONINSIGHTS_CONNECTION_STRING not set — server-side tracing disabled"
      );
      return;
    }

    try {
      const { useAzureMonitor } = await import("@azure/monitor-opentelemetry");

      useAzureMonitor({
        azureMonitorExporterOptions: {
          connectionString,
        },
        instrumentationOptions: {
          http: { enabled: true },
        },
      });

      console.log(
        "[DirectAI] Azure Monitor OpenTelemetry initialized — server-side tracing active"
      );
    } catch (err) {
      console.error(
        "[DirectAI] Failed to initialize Azure Monitor OpenTelemetry:",
        err
      );
    }
  }
}
