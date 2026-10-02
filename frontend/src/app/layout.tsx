import type { Metadata } from "next";
import type { ReactNode } from "react";
import Header from "@/components/header/Header";
import Footer from "@/components/footer/Footer";
import { AuthProvider } from "@/lib/auth-context";
import OnboardingGate from "@/components/onboarding-modal/OnboardingGate";
import InteractionSync from "@/components/recommendation-strip/InteractionSync";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "KDZino - Mua Sắm Thông Minh", template: "%s | KDZino" },
  description: "Nền tảng thương mại điện tử mua sắm thông minh, giao hàng toàn quốc.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <AuthProvider>
          <Header />
          <OnboardingGate />
          <InteractionSync />
          <main>{children}</main>
          <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}
