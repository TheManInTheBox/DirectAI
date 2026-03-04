/**
 * Next.js Middleware — Session Protection
 *
 * Protects /dashboard/* routes. Unauthenticated users are redirected to /login.
 * Public routes (landing, pricing, waitlist, API auth routes) are always accessible.
 */

export { auth as middleware } from "@/lib/auth";

export const config = {
  // Protect dashboard and API management routes
  // Exclude public pages, static assets, and NextAuth API routes
  matcher: ["/dashboard/:path*"],
};
