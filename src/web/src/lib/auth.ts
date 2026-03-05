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
      //
      // REQUIRED ENTRA PORTAL CONFIG (or email falls through to garbage):
      //   1. App Registration → Token Configuration → Add optional claim
      //      → ID Token → check "email" → Save
      //   2. App Registration → API Permissions → Add Microsoft Graph →
      //      Delegated → "email", "openid", "profile" → Grant admin consent
      //   3. User Flow → User attributes → check "Email Address"
      //   4. User Flow → Application claims → check "Email Address"
      {
        id: "entra-external",
        name: "DirectAI",
        type: "oidc",
        issuer: process.env.AUTH_ENTRA_EXTERNAL_ISSUER,
        clientId: process.env.AUTH_ENTRA_EXTERNAL_CLIENT_ID,
        clientSecret: process.env.AUTH_ENTRA_EXTERNAL_CLIENT_SECRET,
        authorization: {
          params: {
            scope: "openid profile email User.Read",
          },
        },
        async profile(profile, tokens) {
          // Extract email from OIDC claims. Entra External ID (CIAM) does NOT
          // include email in the ID token even with optional claims configured.
          // Fallback: use the access token to call Microsoft Graph /me endpoint.
          //
          // Claim sources tried in order:
          //   1. ID token claims (email, preferred_username, upn, emails, etc.)
          //   2. Microsoft Graph /me endpoint via access_token (User.Read scope)
          //   3. OIDC userinfo endpoint via access_token
          //   4. Garbage fallback: {sub}@directai.user

          const isEmail = (v: unknown): v is string =>
            typeof v === "string" && v.includes("@") && !v.endsWith("@directai.user");

          // --- Source 1: ID token claims ---
          const idTokenCandidates = [
            profile.email,
            profile.preferred_username,
            profile.upn,
            (profile.emails as string[] | undefined)?.[0],
            profile.signInNames?.emailAddress,
            (profile.otherMails as string[] | undefined)?.[0],
          ];

          let email = idTokenCandidates.find(isEmail);

          // --- Source 2: Microsoft Graph /me (requires User.Read scope) ---
          if (!email && tokens.access_token) {
            try {
              const graphRes = await fetch(
                "https://graph.microsoft.com/v1.0/me?$select=mail,otherMails,userPrincipalName",
                { headers: { Authorization: `Bearer ${tokens.access_token}` } }
              );
              if (graphRes.ok) {
                const me = await graphRes.json();
                console.log(
                  `[auth] Graph /me response: mail=${me.mail}, upn=${me.userPrincipalName}, ` +
                  `otherMails=${JSON.stringify(me.otherMails)}`
                );
                const graphCandidates = [
                  me.mail,
                  me.userPrincipalName,
                  ...(me.otherMails ?? []),
                ];
                email = graphCandidates.find(isEmail);
              } else {
                console.warn(
                  `[auth] Graph /me failed: ${graphRes.status} ${graphRes.statusText}`
                );
              }
            } catch (err) {
              console.warn(`[auth] Graph /me fetch error:`, err);
            }
          }

          // --- Source 3: OIDC userinfo endpoint ---
          if (!email && tokens.access_token) {
            try {
              const userinfoRes = await fetch(
                "https://graph.microsoft.com/oidc/userinfo",
                { headers: { Authorization: `Bearer ${tokens.access_token}` } }
              );
              if (userinfoRes.ok) {
                const info = await userinfoRes.json();
                console.log(
                  `[auth] OIDC userinfo response: email=${info.email}, keys=[${Object.keys(info).join(",")}]`
                );
                if (isEmail(info.email)) email = info.email;
              } else {
                console.warn(
                  `[auth] OIDC userinfo failed: ${userinfoRes.status} ${userinfoRes.statusText}`
                );
              }
            } catch (err) {
              console.warn(`[auth] OIDC userinfo fetch error:`, err);
            }
          }

          // --- Source 4: garbage fallback ---
          if (!email) email = `${profile.sub}@directai.user`;

          const name =
            profile.name ??
            profile.given_name ??
            (profile.preferred_username !== email ? profile.preferred_username : undefined) ??
            email.split("@")[0];

          console.log(
            `[auth] OIDC profile: sub=${profile.sub}, email=${email}, name=${name}, ` +
            `has_email_claim=${!!profile.email}, has_preferred_username=${!!profile.preferred_username}, ` +
            `has_upn=${!!profile.upn}, raw_keys=[${Object.keys(profile).join(",")}]`
          );

          if (email.endsWith("@directai.user")) {
            console.error(
              `[auth] WARNING: No email found in OIDC claims OR Graph /me for sub=${profile.sub}. ` +
              `Check Entra External ID token configuration. Claims received: ${JSON.stringify(profile)}`
            );
          }

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
      async jwt({ token, user, profile, account }) {
        // On first sign-in, user object is available — persist the DB id in the token.
        // The profile() callback already resolved email via Graph if needed.
        if (user) {
          token.sub = user.id;
          token.name = user.name;
          token.email = user.email;
          token.picture = user.image;
        }
        // On subsequent OIDC sign-ins, profile has fresh claims — update the token.
        // If profile doesn't have email (CIAM issue), use Graph /me via access_token.
        if (profile) {
          const isEmail = (v: unknown): v is string =>
            typeof v === "string" && v.includes("@") && !v.endsWith("@directai.user");

          const freshName =
            profile.name ??
            profile.given_name ??
            profile.preferred_username ??
            token.name;

          const emailCandidates = [
            profile.email,
            profile.preferred_username,
            profile.upn,
            (profile.emails as string[] | undefined)?.[0],
          ];
          let freshEmail = emailCandidates.find(isEmail);

          // Graph /me fallback (same as profile callback)
          if (!freshEmail && account?.access_token) {
            try {
              const graphRes = await fetch(
                "https://graph.microsoft.com/v1.0/me?$select=mail,otherMails,userPrincipalName",
                { headers: { Authorization: `Bearer ${account.access_token}` } }
              );
              if (graphRes.ok) {
                const me = await graphRes.json();
                const graphCandidates = [
                  me.mail,
                  me.userPrincipalName,
                  ...(me.otherMails ?? []),
                ];
                freshEmail = graphCandidates.find(isEmail);
              }
            } catch {
              // Silently fall through — email will come from existing token
            }
          }

          token.name = freshName;
          token.email = freshEmail ?? token.email;
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
      async signIn({ user, profile, account }) {
        // Update user profile from OIDC claims on every sign-in
        // (Drizzle adapter only writes on createUser, never updates)
        if (user.id && profile && process.env.DATABASE_URL) {
          try {
            const isEmail = (v: unknown): v is string =>
              typeof v === "string" && v.includes("@") && !v.endsWith("@directai.user");

            const freshName =
              profile.name ??
              profile.given_name ??
              profile.preferred_username ??
              undefined;

            const emailCandidates = [
              profile.email,
              profile.preferred_username,
              profile.upn,
              (profile.emails as string[] | undefined)?.[0],
            ];
            let freshEmail = emailCandidates.find(isEmail);

            // Graph /me fallback for CIAM tenants that don't emit email in ID token
            if (!freshEmail && account?.access_token) {
              try {
                const graphRes = await fetch(
                  "https://graph.microsoft.com/v1.0/me?$select=mail,otherMails,userPrincipalName",
                  { headers: { Authorization: `Bearer ${account.access_token}` } }
                );
                if (graphRes.ok) {
                  const me = await graphRes.json();
                  const graphCandidates = [
                    me.mail,
                    me.userPrincipalName,
                    ...(me.otherMails ?? []),
                  ];
                  freshEmail = graphCandidates.find(isEmail);
                }
              } catch {
                // Silently fall through
              }
            }

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
