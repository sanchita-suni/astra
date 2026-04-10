import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Astra starter",
  description: "Scaffolded by Astra. Edit freely.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
