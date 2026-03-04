"use client";

import { useState, useTransition } from "react";
import { createApiKey, revokeApiKey } from "./actions";
import { Key, Copy, Check, Trash2, Plus, AlertTriangle } from "lucide-react";

type ApiKeyRow = {
  id: string;
  keyPrefix: string;
  name: string;
  createdAt: Date;
  lastUsedAt: Date | null;
  revokedAt: Date | null;
};

export function ApiKeyTable({ initialKeys }: { initialKeys: ApiKeyRow[] }) {
  const [keys, setKeys] = useState(initialKeys);
  const [newKeyName, setNewKeyName] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const handleCreate = () => {
    if (!newKeyName.trim()) return;
    setError(null);
    startTransition(async () => {
      try {
        const result = await createApiKey(newKeyName.trim());
        setNewKey(result.key);
        setKeys((prev) => [
          {
            id: result.id,
            keyPrefix: result.keyPrefix,
            name: result.name,
            createdAt: result.createdAt,
            lastUsedAt: null,
            revokedAt: null,
          },
          ...prev,
        ]);
        setNewKeyName("");
        setShowCreate(false);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to create key");
      }
    });
  };

  const handleRevoke = (id: string) => {
    if (!confirm("Revoke this API key? Any requests using it will immediately fail. This cannot be undone."))
      return;
    startTransition(async () => {
      try {
        await revokeApiKey(id);
        setKeys((prev) =>
          prev.map((k) =>
            k.id === id ? { ...k, revokedAt: new Date() } : k
          )
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to revoke key");
      }
    });
  };

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const activeKeys = keys.filter((k) => !k.revokedAt);
  const revokedKeys = keys.filter((k) => k.revokedAt);

  return (
    <div className="space-y-6">
      {/* New key banner — show-once warning */}
      {newKey && (
        <div className="rounded-xl border border-yellow-600/50 bg-yellow-950/20 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-yellow-500" />
            <div className="flex-1 space-y-2">
              <p className="text-sm font-medium text-yellow-200">
                Copy your API key now — it won&apos;t be shown again.
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 break-all rounded-lg bg-gray-950 px-3 py-2 font-mono text-sm text-gray-200">
                  {newKey}
                </code>
                <button
                  onClick={() => handleCopy(newKey)}
                  className="shrink-0 rounded-lg border border-gray-700 bg-gray-800 p-2 text-gray-300 transition hover:text-white"
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-green-400" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </button>
              </div>
              <button
                onClick={() => setNewKey(null)}
                className="text-xs text-yellow-400 hover:underline"
              >
                I&apos;ve saved my key
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="rounded-lg border border-red-700/50 bg-red-950/20 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Header + create button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Active Keys</h2>
          <p className="text-sm text-gray-400">
            {activeKeys.length} key{activeKeys.length !== 1 ? "s" : ""}
          </p>
        </div>
        {!showCreate ? (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500"
          >
            <Plus className="h-4 w-4" />
            Create Key
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              placeholder="Key name (e.g., production)"
              className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white placeholder-gray-500 outline-none focus:border-blue-500"
              autoFocus
              disabled={isPending}
            />
            <button
              onClick={handleCreate}
              disabled={isPending || !newKeyName.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
            >
              {isPending ? "Creating..." : "Create"}
            </button>
            <button
              onClick={() => {
                setShowCreate(false);
                setNewKeyName("");
              }}
              className="rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-400 transition hover:text-white"
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {/* Active keys table */}
      {activeKeys.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-gray-800">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/50">
                <th className="px-4 py-3 font-medium text-gray-400">Name</th>
                <th className="px-4 py-3 font-medium text-gray-400">Key</th>
                <th className="px-4 py-3 font-medium text-gray-400">
                  Created
                </th>
                <th className="px-4 py-3 font-medium text-gray-400">
                  Last Used
                </th>
                <th className="px-4 py-3 font-medium text-gray-400" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {activeKeys.map((key) => (
                <tr key={key.id} className="hover:bg-gray-900/30">
                  <td className="px-4 py-3 font-medium text-white">
                    {key.name}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-400">
                    {key.keyPrefix}...
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {new Date(key.createdAt).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {key.lastUsedAt
                      ? new Date(key.lastUsedAt).toLocaleDateString()
                      : "Never"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleRevoke(key.id)}
                      disabled={isPending}
                      className="rounded-lg p-1.5 text-gray-500 transition hover:bg-red-950/50 hover:text-red-400"
                      title="Revoke key"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-xl border border-gray-800 bg-gray-900/30 p-12 text-center">
          <Key className="mx-auto h-10 w-10 text-gray-600" />
          <p className="mt-4 text-gray-400">No API keys yet</p>
          <p className="mt-1 text-sm text-gray-500">
            Create your first key to start making API requests.
          </p>
        </div>
      )}

      {/* Revoked keys */}
      {revokedKeys.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-500">Revoked Keys</h3>
          <div className="overflow-hidden rounded-xl border border-gray-800/50">
            <table className="w-full text-left text-sm">
              <tbody className="divide-y divide-gray-800/50">
                {revokedKeys.map((key) => (
                  <tr key={key.id} className="opacity-50">
                    <td className="px-4 py-2 text-gray-500">{key.name}</td>
                    <td className="px-4 py-2 font-mono text-gray-600">
                      {key.keyPrefix}...
                    </td>
                    <td className="px-4 py-2 text-gray-600">
                      Revoked{" "}
                      {new Date(key.revokedAt!).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
