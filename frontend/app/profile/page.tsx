"use client";

import { AppShell } from "@/components/AppShell";
import { ProfileView } from "@/components/ProfileView";
import { useAuth } from "@/lib/auth";

export default function MyProfilePage() {
  const { user } = useAuth();

  return (
    <AppShell>
      <h1 className="mb-4 text-lg font-semibold text-ink-900">My Profile</h1>
      {user && <ProfileView userId={user.id} isSelf />}
    </AppShell>
  );
}
