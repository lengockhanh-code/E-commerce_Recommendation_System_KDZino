import { notFound, redirect } from "next/navigation";
import AccountPage from "../AccountPage";
import { accountSections, type AccountSection } from "../account-data";

export default async function AccountSectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (section === "logout") redirect("/profile");
  if (section === "overview" || !Object.prototype.hasOwnProperty.call(accountSections, section)) notFound();
  return <AccountPage key={section} section={section as AccountSection} />;
}
