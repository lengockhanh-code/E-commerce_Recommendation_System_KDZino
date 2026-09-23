import { notFound } from "next/navigation";
import { getProduct } from "@/lib/catalog-server";
import ProductDetail from "./ProductDetail";
import "./product-detail.css";

export const runtime = "nodejs";
export default async function ProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const product = await getProduct((await params).id);
  if (!product) notFound();
  return <ProductDetail key={product.id} product={product} />;
}
