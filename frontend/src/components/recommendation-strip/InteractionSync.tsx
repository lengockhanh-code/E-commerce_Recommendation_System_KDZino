"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { flushPendingInteractions, pendingInteractionCount } from "@/lib/recommendations-client";

export default function InteractionSync() {
  const { user, isLoading } = useAuth();
  const [pending, setPending] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const refresh = useCallback(() => setPending(pendingInteractionCount()), []);
  const retry = useCallback(async () => {
    setSyncing(true);
    try { await flushPendingInteractions(); } finally { refresh(); setSyncing(false); }
  }, [refresh]);
  useEffect(() => {
    if (isLoading) return;
    refresh();
    void retry();
    const resume = () => { if (document.visibilityState === "visible") void retry(); };
    const timer = window.setInterval(() => { if (pendingInteractionCount()) void retry(); }, 30000);
    window.addEventListener("online", retry);
    window.addEventListener("pageshow", retry);
    window.addEventListener("merrec:interaction-queue-changed", refresh);
    document.addEventListener("visibilitychange", resume);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("online", retry);
      window.removeEventListener("pageshow", retry);
      window.removeEventListener("merrec:interaction-queue-changed", refresh);
      document.removeEventListener("visibilitychange", resume);
    };
  }, [isLoading, user?.id, refresh, retry]);
  if (!pending) return null;
  return <div className="container-custom" role="status" aria-live="polite" style={{ padding: "8px 0", color: "#8a4b00" }}>
    {pending} tương tác chưa được đồng bộ. {syncing ? "Đang đồng bộ…" : <button type="button" onClick={() => void retry()}>Thử lại</button>}
  </div>;
}
