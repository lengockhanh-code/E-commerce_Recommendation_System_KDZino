import {
  getProvinces,
  getDistrictsByProvinceCode,
  getWardsByDistrictCode,
} from "sub-vn";

export const runtime = "nodejs";

const OPENAPI_BASE = "https://provinces.openapi.vn/api";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const type = searchParams.get("type") || "p";
  const code = searchParams.get("code");

  try {
    let targetUrl = `${OPENAPI_BASE}/p/`;
    if (type === "d" && code) {
      targetUrl = `${OPENAPI_BASE}/p/${code}?depth=2`;
    } else if (type === "w" && code) {
      targetUrl = `${OPENAPI_BASE}/d/${code}?depth=2`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 1500);

    const apiRes = await fetch(targetUrl, {
      headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" },
      signal: controller.signal,
    }).finally(() => clearTimeout(timeoutId));

    if (apiRes.ok) {
      const data = await apiRes.json();
      return Response.json(data);
    }
  } catch {
    // Silent catch, fallback to sub-vn
  }

  // Resilient fallback using sub-vn official dataset
  try {
    if (type === "p") {
      const provs = getProvinces().map((p: any) => ({ code: String(p.code), name: p.name }));
      return Response.json(provs);
    } else if (type === "d" && code) {
      const formattedCode = String(code).padStart(2, "0");
      const dists = getDistrictsByProvinceCode(formattedCode);
      if (dists && dists.length > 0) {
        return Response.json({
          districts: dists.map((d: any) => ({ code: String(d.code), name: d.name })),
        });
      }
    } else if (type === "w" && code) {
      const formattedCode = String(code).padStart(3, "0");
      const wards = getWardsByDistrictCode(formattedCode);
      if (wards && wards.length > 0) {
        return Response.json({
          wards: wards.map((w: any) => ({ code: String(w.code), name: w.name })),
        });
      }
    }
  } catch {
    // Silent catch
  }

  return Response.json({ error: "Location data unavailable" }, { status: 502 });
}
