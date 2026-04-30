"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export function RefreshAllButton({ brandId }: { brandId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/admin/refresh/${brandId}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "refresh failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={refresh}
        disabled={busy}
        title="Re-run detection + LangGraph workflow"
        className={cn(
          "inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-700 shadow-sm transition",
          busy
            ? "cursor-not-allowed opacity-60"
            : "hover:bg-zinc-50 hover:text-zinc-900",
        )}
      >
        {busy ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Sparkles className="h-4 w-4" />
        )}
        {busy ? "Refreshing…" : "Refresh insights"}
      </button>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
