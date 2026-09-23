// Storefront conversion rate, not a live bank quote. Next.js embeds this at build time.
const configuredRate = Number(process.env.NEXT_PUBLIC_USD_TO_VND_RATE || 26000);
export const USD_TO_VND_RATE = Number.isFinite(configuredRate) && configuredRate > 0
  ? configuredRate : 26000;

export function toVND(amount: number, sourceCurrency = "USD"): number {
  if (!Number.isFinite(amount)) throw new Error("Invalid price");
  if (sourceCurrency === "VND") return Math.round(amount);
  if (sourceCurrency !== "USD") throw new Error(`Unsupported currency: ${sourceCurrency}`);
  return Math.round(amount * USD_TO_VND_RATE);
}

const vndFormatter = new Intl.NumberFormat("vi-VN", {
  style: "currency", currency: "VND", maximumFractionDigits: 0,
});

// Formats an amount already converted to VND; does not convert a second time.
export const formatVND = (amount: number) => vndFormatter.format(amount);
export const formatPrice = (amount: number, sourceCurrency = "USD") =>
  formatVND(toVND(amount, sourceCurrency));
