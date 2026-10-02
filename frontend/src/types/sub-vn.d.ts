declare module 'sub-vn' {
  export function getProvinces(): Array<{ code: string; name: string }>;
  export function getDistrictsByProvinceCode(code: string): Array<{ code: string; name: string }>;
  export function getWardsByDistrictCode(code: string): Array<{ code: string; name: string }>;
  const subVn: any;
  export default subVn;
}
