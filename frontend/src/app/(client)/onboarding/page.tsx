"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import OnboardingModal from "@/components/onboarding-modal/OnboardingModal";
import { useAuth } from "@/lib/auth-context";
import { preferencesRequest, type Preferences } from "@/lib/preferences-client";

export default function OnboardingPage() {
  const router = useRouter();
  const { user, token, isLoading } = useAuth();
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!token || isLoading) return;
    let active = true;
    preferencesRequest(token).then((value) => {
      if (active) { setPreferences(value); setError(""); }
    }).catch((error) => { if (active) setError(error.message); });
    return () => { active = false; };
  }, [token, isLoading, attempt]);
  if (isLoading) return <p role="status">Đang kiểm tra tài khoản…</p>;
  if (!user || !token) return <p>Vui lòng <Link href="/login?next=/onboarding">đăng nhập</Link> để lưu sở thích.</p>;
  if (error) return <div role="alert" className="container-custom"><p>{error}</p><button onClick={() => setAttempt((value) => value + 1)}>Thử lại</button></div>;
  if (!preferences) return <p role="status">Đang tải sở thích…</p>;
  return <OnboardingModal key={user.id} isOpen initialCategories={preferences.categories} onClose={() => router.replace("/")} />;
}
