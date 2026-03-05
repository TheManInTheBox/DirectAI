/**
 * NextAuth v5 Configuration — Entra External ID
 *
 * Uses Microsoft Entra External ID as the OIDC provider for customer-facing
 * authentication. Sessions and accounts stored in PostgreSQL via Drizzle adapter.
 *
 * Environment variables required:
 *   AUTH_SECRET                          — NextAuth session encryption secret
 *   AUTH_ENTRA_EXTERNAL_ISSUER           — https://{subdomain}.ciamlogin.com/{tenant-id}/v2.0
 *   AUTH_ENTRA_EXTERNAL_CLIENT_ID        — App registration client ID in external tenant
 *   AUTH_ENTRA_EXTERNAL_CLIENT_SECRET    — App registration client secret
 *   DATABASE_URL                         — PostgreSQL connection string
 */

import NextAuth from "next-auth";
import type { NextAuthConfig } from "next-auth";
import { DrizzleAdapter } from "@auth/drizzle-adapter";
import { getDb } from "@/lib/db";
import { users, accounts, sessions, verificationTokens } from "@/lib/db/schema";

function buildAuthConfig(): NextAuthConfig {
  return {
    // Only attach the Drizzle adapter when DATABASE_URL is available (runtime, not build time)
    ...(process.env.DATABASE_URL
      ? {
          adapter: DrizzleAdapter(getDb(), {
            usersTable: users,
            accountsTable: accounts,
            sessionsTable: sessions,
            verificationTokensTable: verificationTokens,
          }),
        }
      : {}),

    providers: [
      // Microsoft Entra External ID — OIDC provider
      // Supports Google (native), GitHub (custom OIDC federation), email+OTP
      {
        id: "entra-external",
        name: "DirectAI",
        type: "oidc",
        issuer: process.env.AUTH_ENTRA_EXTERNAL_ISSUER,
        clientId: process.env.AUTH_ENTRA_EXTERNAL_CLIENT_ID,
        clientSecret: process.env.AUTH_ENTRA_EXTERNAL_CLIENT_SECRET,
        authorization: {
          params: {
            scope: "openid profile email",
          },
        },
        profile(profile) {
          // Entra External ID may return email in various claim locations
          // depending on identity provider (MSA, Google, email+OTP, etc.)
          const email =
            profile.email ??
            profile.preferred_username ??
            profile.emails?.[0] ??
            profile.signInNames?.emailAddress ??
            profile.otherMails?.[0] ??
            `${profile.sub}@directai.user`;

          const name =
            profile.name ??
            profile.given_name ??
            profile.preferred_username ??
            email.split("@")[0];

          console.log(`[auth] OIDC profile claims: sub=${profile.sub}, email=${email}, name=${name}, raw_keys=${Object.keys(profile).join(",")}`);

          return {
            id: profile.sub,
            name,
            email,
            image: profile.picture ?? null,
          };
        },
      },
    ],

    session: {
      // Always use JWT — Edge middleware can't use postgres TCP sockets.
      // Drizzle adapter still handles user/account creation in the DB.
      strategy: "jwt",
      maxAge: 30 * 24 * 60 * 60, // 30 days
      updateAge: 24 * 60 * 60, // Refresh session every 24 hours
    },

    pages: {
      signIn: "/login",
      error: "/login",
    },

    callbacks: {
      async jwt({ token, user, profile }) {
        // On first sign-in, user object is available — persist the DB id in the token
        if (user) {
          token.sub = user.id;
          token.name = user.name;
          token.email = user.email;
          token.picture = user.image;
        }
        // On subsequent OIDC sign-ins, profile has fresh claims — update the token
        if (profile) {
          const freshName =
            profile.name ??
            profile.given_name ??
            profile.preferred_username ??
            token.name;
          const freshEmail =
            profile.email ??
            profile.preferred_username ??
            (profile.emails as string[] | undefined)?.[0] ??
            token.email;
          token.name = freshName;
          token.email = freshEmail;
          token.picture = (profile.picture as string) ?? token.picture;
        }
        return token;
      },
      async session({ session, token }) {
        // Expose user ID + fresh profile data from JWT in the session
        if (session.user && token.sub) {
          session.user.id = token.sub;
          session.user.name = token.name as string;
          session.user.email = token.email as string;
          session.user.image = token.picture as string | null;
        }
        return session;
      },
      async redirect({ url, baseUrl }) {
        // After sign-in, redirect to dashboard
        if (url.startsWith("/")) return `${baseUrl}${url}`;
        if (new URL(url).origin === baseUrl) return url;
        return `${baseUrl}/dashboard`;
      },
    },

    events: {
      async signIn({ user, profile }) {
        // Update user profile from OIDC claims on every sign-in
        // (Drizzle adapter only writes on createUser, never updates)
        if (user.id && profile && process.env.DATABASE_URL) {
          try {
            const freshName =
              profile.name ??
              profile.given_name ??
              profile.preferred_username ??
              undefined;
            const freshEmail =
              profile.email ??
              profile.preferred_username ??
              (profile.emails as string[] | undefined)?.[0] ??
              undefined;
            const freshImage = (profile.picture as string) ?? undefined;

            // Only update if we have something real to write
            if (freshName || freshEmail || freshImage) {
              const { eq } = await import("drizzle-orm");
              const db = getDb();
              await db
                .update(users)
                .set({
                  ...(freshName ? { name: freshName } : {}),
                  ...(freshEmail && !freshEmail.endsWith("@directai.user")
                    ? { email: freshEmail }
                    : {}),
                  ...(freshImage ? { image: freshImage } : {}),
                  updatedAt: new Date(),
                })
                .where(eq(users.id, user.id));
              console.log(
                `[auth] Updated user profile on sign-in: ${user.id} → name=${freshName}, email=${freshEmail}`
              );
            }
          } catch (err) {
            // Don't fail sign-in if DB update fails
            console.error(`[auth] Failed to update user profile for ${user.id}:`, err);
          }
        }
      },
      async createUser({ user }) {
        // Create Stripe customer on first sign-up
        if (user.id && user.email) {
          try {
            const { createStripeCustomer } = await import("@/lib/stripe/customers");
            await createStripeCustomer(user.id, user.email, user.name);
            console.log(`[auth] New user created with Stripe customer: ${user.id} (${user.email})`);
          } catch (err) {
            // Don't fail sign-up if Stripe is unavailable — customer sync can be retried
            console.error(`[auth] Failed to create Stripe customer for ${user.id}:`, err);
          }
        }
      },
    },

    trustHost: true,
    debug: process.env.NODE_ENV === "development",
  };
}

export const {
  handlers,
  auth,
  signIn,
  signOut,
} = NextAuth(buildAuthConfig);
