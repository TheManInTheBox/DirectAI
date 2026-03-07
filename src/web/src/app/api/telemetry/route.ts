/**
 * Telemetry Config API Route
 *
 * Returns the Application Insights connection string at runtime.
 * This is needed because static pages are pre-rendered at build time
 * when the env var isn't available. Client components fetch from this
 * endpoint to get the runtime connection string.
 *
 * The connection string is NOT a secret — it contains the instrumentation
 * key which is designed to be public (embedded in browser JS).
 */

export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({
    connectionString:
      process.env.APPLICATIONINSIGHTS_CONNECTION_STRING || null,
  });
}
