"use client";

import { use } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { ProfileView } from "@/components/ProfileView";
import { useAuth } from "@/lib/auth";

export default function EmployeePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user } = useAuth();
  const userId = Number(id);

  return (
    <AppShell>
      <div className="mb-4 flex items-center gap-2 text-sm">
        <Link href="/employees" className="text-brand-600 hover:text-brand-700">
          Employees
        </Link>
        <span className="text-ink-300">/</span>
        <span className="text-ink-500">Profile</span>
      </div>
      {user && <ProfileView userId={userId} isSelf={user.id === userId} />}
    </AppShell>
  );
}
