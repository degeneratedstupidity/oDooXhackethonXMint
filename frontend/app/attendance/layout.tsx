import type { Metadata } from "next";

export const metadata: Metadata = { title: "Attendance — Dayflow" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
