import type { Metadata } from "next";

export const metadata: Metadata = { title: "Time Off — Dayflow" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
