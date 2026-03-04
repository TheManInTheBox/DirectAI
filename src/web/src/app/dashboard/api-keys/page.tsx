import type { Metadata } from "next";
import { listApiKeys } from "./actions";
import { ApiKeyTable } from "./api-key-table";

export const metadata: Metadata = {
  title: "API Keys",
  description: "Create and manage your DirectAI API keys.",
};

export default async function ApiKeysPage() {
  const keys = await listApiKeys();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">API Keys</h1>
        <p className="mt-1 text-gray-400">
          Create and manage API keys for authenticating with the DirectAI
          inference API. Keys use Bearer token authentication.
        </p>
      </div>

      <ApiKeyTable initialKeys={keys} />
    </div>
  );
}
