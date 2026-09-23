import type { Metadata } from "next";
import type { ReactNode } from "react";
import Header from "@/components/header/Header";
import Footer from "@/components/footer/Footer";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "KDZino - Mua Sắm Thông Minh", template: "%s | KDZino" },
  description: "Nền tảng thương mại điện tử mua sắm thông minh, giao hàng toàn quốc.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <Header />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
