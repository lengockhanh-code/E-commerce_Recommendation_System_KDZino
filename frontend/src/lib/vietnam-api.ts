// Official Vietnam Administrative Divisions API & Sub-VN Fallback
// Provides 100% complete data for all 63 Provinces, Districts & Wards of Vietnam.

import {
  getProvinceObjects,
  getDistrictObjects,
  getWardObjects,
} from "./vietnamLocations";

export interface LocationItem {
  code: string | number;
  name: string;
}

const OPENAPI_BASE = "https://provinces.openapi.vn/api";

export async function fetchProvincesApi(): Promise<LocationItem[]> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);
    const res = await fetch(`${OPENAPI_BASE}/p/`, { cache: "force-cache", signal: controller.signal }).finally(() => clearTimeout(timeoutId));
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        return data.map((item: any) => ({ code: item.code, name: item.name }));
      }
    }
  } catch {
    // Non-blocking catch
  }

  try {
    const res = await fetch("/api/locations?type=p");
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        return data.map((item: any) => ({ code: item.code, name: item.name }));
      }
    }
  } catch {
    // Non-blocking catch
  }

  // Guaranteed complete local fallback (63 provinces)
  return getProvinceObjects();
}

export async function fetchDistrictsApi(provinceCodeOrName: string | number): Promise<LocationItem[]> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);
    const res = await fetch(`${OPENAPI_BASE}/p/${provinceCodeOrName}?depth=2`, { cache: "force-cache", signal: controller.signal }).finally(() => clearTimeout(timeoutId));
    if (res.ok) {
      const data = await res.json();
      if (data && Array.isArray(data.districts) && data.districts.length > 0) {
        return data.districts.map((item: any) => ({ code: item.code, name: item.name }));
      }
    }
  } catch {
    // Non-blocking catch
  }

  try {
    const res = await fetch(`/api/locations?type=d&code=${provinceCodeOrName}`);
    if (res.ok) {
      const data = await res.json();
      if (data && Array.isArray(data.districts) && data.districts.length > 0) {
        return data.districts.map((item: any) => ({ code: item.code, name: item.name }));
      }
    }
  } catch {
    // Non-blocking catch
  }

  // Guaranteed complete local fallback
  return getDistrictObjects(String(provinceCodeOrName));
}

export async function fetchWardsApi(districtCodeOrName: string | number, provinceName?: string): Promise<LocationItem[]> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);
    const res = await fetch(`${OPENAPI_BASE}/d/${districtCodeOrName}?depth=2`, { cache: "force-cache", signal: controller.signal }).finally(() => clearTimeout(timeoutId));
    if (res.ok) {
      const data = await res.json();
      if (data && Array.isArray(data.wards) && data.wards.length > 0) {
        return data.wards.map((item: any) => ({ code: item.code, name: item.name }));
      }
    }
  } catch {
    // Non-blocking catch
  }

  try {
    const res = await fetch(`/api/locations?type=w&code=${districtCodeOrName}`);
    if (res.ok) {
      const data = await res.json();
      if (data && Array.isArray(data.wards) && data.wards.length > 0) {
        return data.wards.map((item: any) => ({ code: item.code, name: item.name }));
      }
    }
  } catch {
    // Non-blocking catch
  }

  // Guaranteed complete local fallback
  return getWardObjects(String(districtCodeOrName), provinceName);
}
