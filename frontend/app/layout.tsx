import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { MockDataNotice } from "@/components/DataSource";
import { OverridesBanner } from "@/components/OverridesBanner";
import { Sidebar } from "@/components/Sidebar";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ExpressBus AI",
  description: "AI-powered express bus resource optimization",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col md:flex-row">
        <Sidebar />
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 sm:py-8">
          <div className="mx-auto max-w-7xl">
            <MockDataNotice />
            <OverridesBanner />
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
