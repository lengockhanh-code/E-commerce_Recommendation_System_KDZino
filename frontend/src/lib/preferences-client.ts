export interface Preferences { categories: string[]; completed: boolean }

export async function preferencesRequest(token: string, categories?: string[]): Promise<Preferences> {
  const response = await fetch("/api/preferences", {
    method: categories === undefined ? "GET" : "PUT",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: categories === undefined ? undefined : JSON.stringify({ categories }),
    cache: "no-store",
    signal: AbortSignal.timeout(12000),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Chưa thể đọc hoặc lưu sở thích.");
  return result;
}
