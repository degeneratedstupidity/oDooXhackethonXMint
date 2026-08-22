"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Field } from "@/components/Field";
import { PasswordField } from "@/components/PasswordField";
import { useAuth } from "@/lib/auth";
import type { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const signedIn = await login(loginId.trim(), password);
      router.push(signedIn?.must_change_password ? "/change-password" : "/employees");
    } catch (caught) {
      const apiError = caught as ApiError;
      // The token endpoint returns a generic 401; say something more useful.
      setError(
        apiError.status === 401
          ? { ...apiError, message: "Incorrect login ID or password." }
          : apiError,
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="rounded-2xl border border-ink-200 bg-white p-8 shadow-sm">
          <div className="mb-8 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-xl font-bold text-white">
              D
            </div>
            <h1 className="text-xl font-semibold text-ink-900">Dayflow</h1>
            <p className="mt-1 text-sm text-ink-500">Sign in to your workspace</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <Field
              label="Login ID / Email"
              name="login_id"
              value={loginId}
              onChange={setLoginId}
              placeholder="OIJODO20260001"
              autoComplete="username"
              required
            />
            <PasswordField
              label="Password"
              name="password"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
              required
            />

            {error && (
              <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                {error.message}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting || !loginId || !password}
              className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition
                hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "Signing in…" : "Sign In"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-ink-500">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="font-medium text-brand-600 hover:text-brand-700">
              Sign Up
            </Link>
          </p>
        </div>

        <p className="mt-4 text-center text-xs text-ink-400">
          Employees are added by their HR team and receive a generated login ID.
        </p>
      </div>
    </main>
  );
}
