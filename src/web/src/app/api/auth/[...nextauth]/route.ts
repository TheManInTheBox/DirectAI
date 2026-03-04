/**
 * NextAuth API Route Handler
 *
 * Handles all /api/auth/* routes:
 *   GET  /api/auth/signin        — Sign-in page redirect
 *   POST /api/auth/signin/*      — Provider sign-in
 *   GET  /api/auth/callback/*    — OAuth callback
 *   POST /api/auth/signout       — Sign out
 *   GET  /api/auth/session       — Session info (JSON)
 *   GET  /api/auth/csrf          — CSRF token
 */

import { handlers } from "@/lib/auth";
import type { NextRequest } from "next/server";

export async function GET(
  request: NextRequest,
  _context: { params: Promise<{ nextauth: string[] }> }
) {
  return handlers.GET(request);
}

export async function POST(
  request: NextRequest,
  _context: { params: Promise<{ nextauth: string[] }> }
) {
  return handlers.POST(request);
}
