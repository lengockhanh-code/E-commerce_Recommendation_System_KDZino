"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { preferencesRequest } from "@/lib/preferences-client";

export default function OnboardingGate() {
  const { user, token, isLoading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (isLoading || !user || !token || pathname === "/onboarding") return;
    let active = true;
    preferencesRequest(token).then((preferences) => {
      if (!active) return;
      setError("");
      if (!preferences.completed) router.replace("/onboarding");
    }).catch(() => { if (active) setError("Chưa thể kiểm tra sở thích của bạn."); });
    return () => { active = false; };
  }, [user?.id, token, isLoading, pathname, router, attempt]);
  if (!user || pathname === "/onboarding" || !error) return null;
  return <div role="alert" className="container-custom">
    {error} <button onClick={() => setAttempt((value) => value + 1)}>Thử lại</button>
  </div>;
}
