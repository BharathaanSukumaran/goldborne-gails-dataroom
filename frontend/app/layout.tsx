import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Goldborne Gail's Dataroom",
  description: "AI dataroom assistant for Gail's Limited public company information."
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
