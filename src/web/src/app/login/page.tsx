import type { Metadata } from "next";
import { LoginForm } from "./login-form";

export const metadata: Metadata = {
  title: "Sign In",
  description: "Sign in to your DirectAI account to manage API keys, view usage, and configure your models.",
};

export default function LoginPage() {
  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Welcome back
          </h1>
          <p className="mt-2 text-gray-400">
            Sign in to manage your API keys, monitor usage, and configure deployments.
          </p>
        </div>

        {/* Sign-in card */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-8">
          <LoginForm />
        </div>

        {/* Footer note */}
        <p className="text-center text-xs text-gray-500">
          By signing in, you agree to our{" "}
          <a href="/terms" className="text-cyan-400 hover:underline">
            Terms of Service
          </a>{" "}
          and{" "}
          <a href="/privacy" className="text-cyan-400 hover:underline">
            Privacy Policy
          </a>
          .
        </p>
      </div>
    </div>
  );
}
