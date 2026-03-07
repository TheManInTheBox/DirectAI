"use client";

/**
 * Application Insights Browser SDK — Client-Side Telemetry
 *
 * Provides automatic tracking of:
 *   - Page views (every route change in Next.js App Router)
 *   - Page visit time (time spent per page)
 *   - Client-side exceptions (unhandled errors)
 *   - AJAX / fetch dependency calls
 *   - Web Vitals performance metrics
 *   - User sessions (anonymous + authenticated)
 *   - Authenticated user correlation (via NextAuth session)
 *
 * The connection string is fetched at runtime from /api/telemetry
 * to work correctly with both static and dynamic pages.
 */

import { useEffect, useRef, useCallback } from "react";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  ApplicationInsights,
} from "@microsoft/applicationinsights-web";

let appInsightsInstance: ApplicationInsights | null = null;

function initInstance(connectionString: string): ApplicationInsights {
  if (appInsightsInstance) return appInsightsInstance;

  const config = {
    connectionString,
    /* ── Page view tracking ─────────────────────────────────────────── */
    enableAutoRouteTracking: false, // We track manually for App Router compat
    autoTrackPageVisitTime: true, // Track time spent on each page

    /* ── Dependency / AJAX tracking ────────────────────────────────── */
    disableFetchTracking: false,
    enableCorsCorrelation: true,
    enableRequestHeaderTracking: true,
    enableResponseHeaderTracking: true,
    enableAjaxPerfTracking: true,

    /* ── Exception tracking ────────────────────────────────────────── */
    enableUnhandledPromiseRejectionTracking: true,

    /* ── Batching ──────────────────────────────────────────────────── */
    maxBatchInterval: 5000,
    maxBatchSizeInBytes: 102400,

    /* ── Sampling (send everything in dev; reduce in prod if needed) ─ */
    samplingPercentage: 100,

    /* ── Cookie / session ──────────────────────────────────────────── */
    cookieCfg: {
      enabled: true,
    },
  };

  appInsightsInstance = new ApplicationInsights({ config });
  appInsightsInstance.loadAppInsights();

  return appInsightsInstance;
}

export function AppInsightsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const initialized = useRef(false);
  const prevPathname = useRef<string>("");

  // ── Fetch connection string from API route and initialize ─────────────
  useEffect(() => {
    if (initialized.current) return;

    fetch("/api/telemetry")
      .then((res) => res.json())
      .then((data: { connectionString: string | null }) => {
        if (!data.connectionString) return;
        initInstance(data.connectionString);
        initialized.current = true;

        // Track the initial page view after init
        if (pathname) {
          appInsightsInstance?.trackPageView({
            name: document.title,
            uri: pathname,
            properties: { routePath: pathname },
          });
          prevPathname.current = pathname;
        }
      })
      .catch(() => {
        // Telemetry failure should never break the app
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Track page views on route change ──────────────────────────────────
  const trackPageView = useCallback(() => {
    if (!appInsightsInstance || !pathname) return;
    if (pathname === prevPathname.current) return;
    prevPathname.current = pathname;

    appInsightsInstance.trackPageView({
      name: document.title,
      uri: pathname,
      properties: {
        routePath: pathname,
      },
    });
  }, [pathname]);

  useEffect(() => {
    trackPageView();
  }, [trackPageView]);

  // ── Set authenticated user context from NextAuth session ──────────────
  useEffect(() => {
    if (!appInsightsInstance) return;

    if (session?.user?.email) {
      appInsightsInstance.setAuthenticatedUserContext(
        session.user.email,
        undefined, // accountId — not used
        true // storeInCookie for cross-page correlation
      );
    } else {
      appInsightsInstance.clearAuthenticatedUserContext();
    }
  }, [session?.user?.email]);

  return <>{children}</>;
}
