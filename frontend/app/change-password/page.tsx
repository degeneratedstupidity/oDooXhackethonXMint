"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { SecurityTab } from "@/components/SecurityTab";
import { useAuth } from "@/lib/auth";

/** Shown to an employee still using the password generated when their account was
    created. They cannot reach the rest of the app until they replace it. */
export default function ChangePasswordPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    // Once the password has been changed the flag clears and this page is done.
    else if (!user.must_change_password) router.replace("/employees");
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-ink-500">Loading…</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="rounded-2xl border border-ink-200 bg-white p-8 shadow-sm">
          <div className="mb-6">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-xl font-bold text-white">
              D
            </div>
            <h1 className="text-xl font-semibold text-ink-900">Choose your password</h1>
            <p className="mt-1 text-sm text-ink-500">
              Welcome, {user.first_name}. Your account was created with a temporary password.
              Please set your own before continuing.
            </p>
          </div>

          <SecurityTab />

          <button
            onClick={logout}
            className="mt-6 text-sm text-ink-500 underline-offset-2 hover:text-ink-800 hover:underline"
          >
            Sign out instead
          </button>
        </div>
      </div>
    </main>
  );
}
