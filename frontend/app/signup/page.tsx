"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Field } from "@/components/Field";
import { PasswordField } from "@/components/PasswordField";
import { apiFetch, storeTokens } from "@/lib/api";
import type { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Company sign-up. This creates the tenant and its first Admin — employees are
    created from inside the app by Admin/HR, never here. */
export default function SignUpPage() {
  const router = useRouter();
  const { refreshUser } = useAuth();

  const [values, setValues] = useState({
    company_name: "",
    name: "",
    email: "",
    phone: "",
    password: "",
    confirm_password: "",
  });
  const [logo, setLogo] = useState<File | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const update = (key: keyof typeof values) => (value: string) =>
    setValues((current) => ({ ...current, [key]: value }));

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    // Sent as multipart because of the optional logo upload.
    const payload = new FormData();
    Object.entries(values).forEach(([key, value]) => payload.append(key, value));
    if (logo) payload.append("logo", logo);

    try {
      const result = await apiFetch<{ tokens: { access: string; refresh: string } }>(
        "/auth/signup/",
        { method: "POST", body: payload },
      );
      storeTokens(result.tokens);
      await refreshUser();
      router.push("/employees");
    } catch (caught) {
      setError(caught as ApiError);
    } finally {
      setSubmitting(false);
    }
  }

  const fieldErrors = error?.fields ?? {};

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="rounded-2xl border border-ink-200 bg-white p-8 shadow-sm">
          <div className="mb-8 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-xl font-bold text-white">
              D
            </div>
            <h1 className="text-xl font-semibold text-ink-900">Create your workspace</h1>
            <p className="mt-1 text-sm text-ink-500">
              You&apos;ll be set up as the administrator.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <Field
                  label="Company Name"
                  name="company_name"
                  value={values.company_name}
                  onChange={update("company_name")}
                  errors={fieldErrors.company_name}
                  placeholder="Odoo India"
                  required
                />
              </div>
              <label
                title="Upload company logo"
                className="mb-0.5 flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-lg
                  border border-ink-300 bg-ink-50 text-lg transition hover:border-brand-400 hover:bg-brand-50"
              >
                {logo ? "✅" : "⬆️"}
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(event) => setLogo(event.target.files?.[0] ?? null)}
                />
              </label>
            </div>
            {logo && (
              <p className="-mt-2 truncate text-xs text-ink-500">Logo: {logo.name}</p>
            )}

            <Field
              label="Your Name"
              name="name"
              value={values.name}
              onChange={update("name")}
              errors={fieldErrors.name}
              placeholder="John Doe"
              required
            />
            <Field
              label="Email"
              name="email"
              type="email"
              value={values.email}
              onChange={update("email")}
              errors={fieldErrors.email}
              autoComplete="email"
              required
            />
            <Field
              label="Phone"
              name="phone"
              value={values.phone}
              onChange={update("phone")}
              errors={fieldErrors.phone}
            />
            <PasswordField
              label="Password"
              name="password"
              value={values.password}
              onChange={update("password")}
              errors={fieldErrors.password}
              autoComplete="new-password"
              required
            />
            <PasswordField
              label="Confirm Password"
              name="confirm_password"
              value={values.confirm_password}
              onChange={update("confirm_password")}
              errors={fieldErrors.confirm_password}
              autoComplete="new-password"
              required
            />

            {error && !Object.keys(fieldErrors).length && (
              <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                {error.message}
              </p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition
                hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "Creating…" : "Sign Up"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-ink-500">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-brand-600 hover:text-brand-700">
              Sign In
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
