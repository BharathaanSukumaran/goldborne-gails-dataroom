import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Goldborne Capital Intelligence Platform",
  description: "Capital intelligence workspace for company diligence, dataroom evidence, and AI analysis."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
