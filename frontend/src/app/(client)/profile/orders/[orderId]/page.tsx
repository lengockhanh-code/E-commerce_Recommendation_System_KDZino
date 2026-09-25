import { notFound } from "next/navigation";
import AccountPage from "../../AccountPage";
import { demoOrders } from "../../account-data";

export default async function OrderDetailPage({ params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = await params;
  if (!demoOrders.some((order) => order.id === orderId)) notFound();
  return <AccountPage section="orders" orderId={orderId} />;
}
