import { SiApple, SiSamsung, SiXiaomi, SiAsus, SiLg, SiSony, SiDell, SiLenovo } from "react-icons/si";

export const mallBrands = [
  { name: "Apple", Icon: SiApple, color: "#242424", caption: "Apple" },
  { name: "SAMSUNG", Icon: SiSamsung, color: "#1428a0" },
  { name: "Xiaomi", Icon: SiXiaomi, color: "#ff6900", caption: "Xiaomi" },
  { name: "ASUS", Icon: SiAsus, color: "#143779" },
  { name: "LG", Icon: SiLg, color: "#a50034" },
  { name: "SONY", Icon: SiSony, color: "#111111" },
  { name: "DELL", Icon: SiDell, color: "#0076ce" },
  { name: "Lenovo", Icon: SiLenovo, color: "#e2231a" },
];

export default function BrandLogo({ name }: { name: string }) {
  const brand = mallBrands.find((item) => item.name === name);
  if (!brand) return <span>{name}</span>;
  return <span className={`mall-brand-mark mall-brand-${name.toLowerCase()}`} role="img" aria-label={name} style={{ color: brand.color }}>
    <brand.Icon aria-hidden="true" focusable="false" />
    {brand.caption && <span aria-hidden="true">{brand.caption}</span>}
  </span>;
}
