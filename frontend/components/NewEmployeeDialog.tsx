"use client";

import { useEffect, useState } from "react";
import { Field } from "./Field";
import { apiFetch } from "@/lib/api";
import type { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Credentials = { login_id: string; password: string };
type Colleague = { id: number; full_name: string; job_position: string };

/** Add an employee. The system generates their login ID and first password, so the
    dialog's job on success is to show those credentials once. */
export function NewEmployeeDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const { user } = useAuth();
  const [values, setValues] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    role: "employee",
    date_of_joining: new Date().toISOString().slice(0, 10),
    job_position: "",
    department: "",
  });
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [credentials, setCredentials] = useState<Credentials | null>(null);
  const [colleagues, setColleagues] = useState<Colleague[]>([]);
  const [managerId, setManagerId] = useState("");

  useEffect(() => {
    apiFetch<Colleague[]>("/employees/").then(setColleagues).catch(() => setColleagues([]));
  }, []);

  const update = (key: keyof typeof values) => (value: string) =>
    setValues((current) => ({ ...current, [key]: value }));

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await apiFetch<{ credentials: Credentials }>("/employees/", {
        method: "POST",
        body: JSON.stringify({
          ...values,
          manager: managerId ? Number(managerId) : null,
        }),
      });
      setCredentials(result.credentials);
    } catch (caught) {
      setError(caught as ApiError);
    } finally {
      setSubmitting(false);
    }
  }

  const fieldErrors = error?.fields ?? {};

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-employee-title"
    >
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white shadow-xl">
        {credentials ? (
          <div className="p-6">
            <h2 id="new-employee-title" className="text-lg font-semibold text-ink-900">
              Employee added
            </h2>
            <p className="mt-1 text-sm text-ink-500">
              Share these credentials with them. The password is shown only once — they will
              be asked to change it when they first sign in.
            </p>
            <dl className="mt-4 space-y-2 rounded-xl bg-ink-50 p-4 font-mono text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-ink-500">Login ID</dt>
                <dd className="font-semibold text-ink-900">{credentials.login_id}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-ink-500">Password</dt>
                <dd className="font-semibold text-ink-900">{credentials.password}</dd>
              </div>
            </dl>
            <button
              onClick={onCreated}
              className="mt-6 w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
            >
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-6" noValidate>
            <h2 id="new-employee-title" className="text-lg font-semibold text-ink-900">
              New employee
            </h2>
            <p className="mt-1 text-sm text-ink-500">
              Their login ID and first password are generated automatically.
            </p>

            <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field
                label="First name"
                name="first_name"
                value={values.first_name}
                onChange={update("first_name")}
                errors={fieldErrors.first_name}
                required
              />
              <Field
                label="Last name"
                name="last_name"
                value={values.last_name}
                onChange={update("last_name")}
                errors={fieldErrors.last_name}
                required
              />
              <Field
                label="Email"
                name="email"
                type="email"
                value={values.email}
                onChange={update("email")}
                errors={fieldErrors.email}
                required
              />
              <Field
                label="Phone"
                name="phone"
                value={values.phone}
                onChange={update("phone")}
                errors={fieldErrors.phone}
              />
              <Field
                label="Job position"
                name="job_position"
                value={values.job_position}
                onChange={update("job_position")}
                errors={fieldErrors.job_position}
              />
              <Field
                label="Department"
                name="department"
                value={values.department}
                onChange={update("department")}
                errors={fieldErrors.department}
              />
              <Field
                label="Date of joining"
                name="date_of_joining"
                type="date"
                value={values.date_of_joining}
                onChange={update("date_of_joining")}
                errors={fieldErrors.date_of_joining}
                required
              />

              <div className="space-y-1.5">
                <label htmlFor="manager" className="block text-sm font-medium text-ink-700">
                  Manager
                </label>
                <select
                  id="manager"
                  value={managerId}
                  onChange={(event) => setManagerId(event.target.value)}
                  className="w-full rounded-lg border border-ink-300 px-3 py-2.5 text-sm outline-none
                    transition focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
                >
                  <option value="">No manager</option>
                  {colleagues.map((colleague) => (
                    <option key={colleague.id} value={colleague.id}>
                      {colleague.full_name}
                      {colleague.job_position ? ` — ${colleague.job_position}` : ""}
                    </option>
                  ))}
                </select>
                {fieldErrors.manager && (
                  <p className="text-xs text-red-600">{fieldErrors.manager[0]}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label htmlFor="role" className="block text-sm font-medium text-ink-700">
                  Role
                </label>
                <select
                  id="role"
                  value={values.role}
                  onChange={(event) => update("role")(event.target.value)}
                  className="w-full rounded-lg border border-ink-300 px-3 py-2.5 text-sm outline-none
                    transition focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
                >
                  <option value="employee">Employee</option>
                  <option value="hr_officer">HR Officer</option>
                  {/* Only an admin can mint another admin. */}
                  {user?.role === "admin" && <option value="admin">Admin</option>}
                </select>
              </div>
            </div>

            {error && !Object.keys(fieldErrors).length && (
              <p role="alert" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                {error.message}
              </p>
            )}

            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 rounded-lg border border-ink-300 px-4 py-2.5 text-sm font-medium text-ink-700 hover:bg-ink-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="flex-1 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white
                  hover:bg-brand-700 disabled:opacity-50"
              >
                {submitting ? "Adding…" : "Add employee"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
