import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthProvider";

export const metadata: Metadata = {
  title: "AI Avatar Platform",
  description:
    "Create a reusable talking-head avatar from a short video, then generate new videos from any script — fully self-hosted, open-source models only.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
