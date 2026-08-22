"use client";

import { useState } from "react";
import { PasswordField } from "./PasswordField";
import { apiFetch } from "@/lib/api";
import type { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Password change. Employees created by an administrator start with a generated
    password and are asked to replace it here. */
export function SecurityTab() {
  const { user, refreshUser } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [done, setDone] = useState(false);
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setDone(false);
    try {
      await apiFetch("/auth/change-password/", {
        method: "POST",
        body: JSON.stringify({
          current_password: current,
          new_password: next,
          confirm_password: confirm,
        }),
      });
      setCurrent("");
      setNext("");
      setConfirm("");
      setDone(true);
      refreshUser();
    } catch (caught) {
      setError(caught as ApiError);
    } finally {
      setSaving(false);
    }
  }

  const fields = error?.fields ?? {};

  return (
    <form onSubmit={submit} className="max-w-md space-y-4" noValidate>
      {user?.must_change_password && (
        <p className="rounded-lg bg-amber-50 px-3 py-2.5 text-sm text-amber-800">
          You are still using the password generated when your account was created. Please
          choose your own.
        </p>
      )}

      <PasswordField
        label="Current password"
        name="current_password"
        value={current}
        onChange={setCurrent}
        errors={fields.current_password}
        autoComplete="current-password"
        required
      />
      <PasswordField
        label="New password"
        name="new_password"
        value={next}
        onChange={setNext}
        errors={fields.new_password}
        autoComplete="new-password"
        required
      />
      <PasswordField
        label="Confirm new password"
        name="confirm_password"
        value={confirm}
        onChange={setConfirm}
        errors={fields.confirm_password}
        autoComplete="new-password"
        required
      />

      {done && (
        <p className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800">
          Password updated.
        </p>
      )}

      <button
        type="submit"
        disabled={saving || !current || !next}
        className="rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white
          hover:bg-brand-700 disabled:opacity-50"
      >
        {saving ? "Updating…" : "Update password"}
      </button>
    </form>
  );
}
