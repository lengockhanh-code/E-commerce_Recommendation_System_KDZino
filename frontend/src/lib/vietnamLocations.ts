import {
  getProvinces as subGetProvinces,
  getDistrictsByProvinceCode,
  getWardsByDistrictCode,
} from "sub-vn";

export interface DistrictItem {
  code: string;
  name: string;
}

export interface ProvinceItem {
  code: string;
  name: string;
}

export interface WardItem {
  code: string;
  name: string;
}

function normalizeName(str: string): string {
  if (!str) return "";
  return str
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/^(tinh|thanh pho|tp\.|quan|huyen|thi xa|phuong|xa|thi tran)\s+/g, "")
    .trim();
}

/**
 * Returns all 63 official provinces/cities of Vietnam
 */
export function getProvinces(): string[] {
  return subGetProvinces().map((p: any) => p.name);
}

export function getProvinceObjects(): ProvinceItem[] {
  return subGetProvinces().map((p: any) => ({ code: String(p.code), name: p.name }));
}

function findProvinceObj(provinceNameOrCode: string): any {
  if (!provinceNameOrCode) return null;
  const allProvs = subGetProvinces();
  const searchStr = String(provinceNameOrCode).trim();

  return (
    allProvs.find(
      (p: any) =>
        String(p.code) === searchStr ||
        p.name === searchStr ||
        normalizeName(p.name) === normalizeName(searchStr) ||
        p.name.includes(searchStr) ||
        searchStr.includes(p.name)
    ) || null
  );
}

/**
 * Returns all districts for a given province (by name or code)
 */
export function getDistricts(provinceNameOrCode: string): string[] {
  const prov = findProvinceObj(provinceNameOrCode);
  if (!prov) return [];
  const dists = getDistrictsByProvinceCode(prov.code);
  return dists.map((d: any) => d.name);
}

export function getDistrictObjects(provinceNameOrCode: string): DistrictItem[] {
  const prov = findProvinceObj(provinceNameOrCode);
  if (!prov) return [];
  const dists = getDistrictsByProvinceCode(prov.code);
  return dists.map((d: any) => ({ code: String(d.code), name: d.name }));
}

function findDistrictObj(provinceCode: string, districtNameOrCode: string): any {
  if (!districtNameOrCode) return null;
  const dists = getDistrictsByProvinceCode(provinceCode);
  const searchStr = String(districtNameOrCode).trim();

  return (
    dists.find(
      (d: any) =>
        String(d.code) === searchStr ||
        d.name === searchStr ||
        normalizeName(d.name) === normalizeName(searchStr) ||
        d.name.includes(searchStr) ||
        searchStr.includes(d.name)
    ) || null
  );
}

/**
 * Returns all wards for a given district
 */
export function getWards(provinceNameOrCode: string, districtNameOrCode: string): string[] {
  const prov = findProvinceObj(provinceNameOrCode);
  if (!prov) return [];
  const dist = findDistrictObj(prov.code, districtNameOrCode);
  if (!dist) return [];
  const wards = getWardsByDistrictCode(dist.code);
  return wards.map((w: any) => w.name);
}

export function getWardObjects(districtCodeOrName: string, provinceNameOrCode?: string): WardItem[] {
  let distCode = String(districtCodeOrName).trim();
  if (provinceNameOrCode) {
    const prov = findProvinceObj(provinceNameOrCode);
    if (prov) {
      const dist = findDistrictObj(prov.code, districtCodeOrName);
      if (dist) distCode = dist.code;
    }
  }

  const wards = getWardsByDistrictCode(distCode);
  return (wards || []).map((w: any) => ({ code: String(w.code), name: w.name }));
}
