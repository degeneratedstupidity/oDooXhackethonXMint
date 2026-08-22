"use client";

import { useCallback, useEffect, useState } from "react";
import { Avatar } from "./Avatar";
import { Field } from "./Field";
import { SalaryInfo } from "./SalaryInfo";
import { SecurityTab } from "./SecurityTab";
import { apiFetch } from "@/lib/api";
import type { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { EmployeeDetail } from "@/lib/types";

type Tab = "resume" | "private" | "salary" | "security";

/** The employee profile page. Used both for "My Profile" and for viewing a colleague,
    which is read-only unless the viewer is Admin or HR. */
export function ProfileView({ userId, isSelf }: { userId: number; isSelf: boolean }) {
  const { user: viewer, refreshUser } = useAuth();
  const [employee, setEmployee] = useState<EmployeeDetail | null>(null);
  const [tab, setTab] = useState<Tab>("resume");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [saved, setSaved] = useState(false);

  // Admin and HR may edit anyone; everyone may edit their own record.
  const editable = isSelf || Boolean(viewer && viewer.role !== "employee");
  // Salary is administrator-only, matching the API.
  const canSeeSalary = viewer?.role === "admin";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setEmployee(await apiFetch<EmployeeDetail>(`/employees/${userId}/`));
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  function patch(path: string, value: unknown) {
    setEmployee((current) => {
      if (!current) return current;
      const [section, key] = path.split(".");
      if (!key) return { ...current, [section]: value };
      return {
        ...current,
        [section]: { ...(current[section as keyof EmployeeDetail] as object), [key]: value },
      };
    });
  }

  async function save() {
    if (!employee) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await apiFetch<EmployeeDetail>(`/employees/${userId}/`, {
        method: "PATCH",
        body: JSON.stringify({
          first_name: employee.first_name,
          last_name: employee.last_name,
          email: employee.email,
          phone: employee.phone,
          profile: employee.profile,
          bank_detail: employee.bank_detail,
        }),
      });
      setEmployee(updated);
      setSaved(true);
      if (isSelf) refreshUser();
    } catch (caught) {
      setError(caught as ApiError);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="py-16 text-center text-sm text-ink-500">Loading profile…</p>;
  if (!employee) return <p className="py-16 text-center text-sm text-ink-500">Not found.</p>;

  const profileErrors = (error?.fields.profile ?? {}) as unknown as Record<string, string[]>;
  const bankErrors = (error?.fields.bank_detail ?? {}) as unknown as Record<string, string[]>;

  const TABS: { id: Tab; label: string }[] = [
    { id: "resume", label: "Resume" },
    { id: "private", label: "Private Info" },
    ...(canSeeSalary ? [{ id: "salary" as Tab, label: "Salary Info" }] : []),
    ...(isSelf ? [{ id: "security" as Tab, label: "Security" }] : []),
  ];

  return (
    <div className="rounded-xl border border-ink-200 bg-white">
      {/* Identity header */}
      <div className="flex flex-col gap-5 border-b border-ink-200 p-6 sm:flex-row">
        <Avatar name={employee.full_name} src={employee.avatar} size="lg" />

        <div className="grid flex-1 grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
          <div className="space-y-2">
            <h1 className="text-xl font-semibold text-ink-900">{employee.full_name}</h1>
            <p className="text-sm text-ink-500">{employee.profile.job_position || "—"}</p>
            <dl className="space-y-1 text-sm">
              <div className="flex gap-2">
                <dt className="w-20 shrink-0 text-ink-400">Login ID</dt>
                <dd className="font-mono text-ink-700">{employee.login_id}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-20 shrink-0 text-ink-400">Email</dt>
                <dd className="truncate text-ink-700">{employee.email}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-20 shrink-0 text-ink-400">Mobile</dt>
                <dd className="text-ink-700">{employee.phone || "—"}</dd>
              </div>
            </dl>
          </div>

          <dl className="space-y-1 text-sm">
            <div className="flex gap-2">
              <dt className="w-24 shrink-0 text-ink-400">Company</dt>
              <dd className="text-ink-700">{employee.company_name}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 shrink-0 text-ink-400">Department</dt>
              <dd className="text-ink-700">{employee.profile.department || "—"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 shrink-0 text-ink-400">Manager</dt>
              <dd className="text-ink-700">{employee.profile.manager_name || "—"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 shrink-0 text-ink-400">Location</dt>
              <dd className="text-ink-700">{employee.profile.location || "—"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-24 shrink-0 text-ink-400">Joined</dt>
              <dd className="text-ink-700">
                {new Date(employee.date_of_joining).toLocaleDateString()}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 overflow-x-auto border-b border-ink-200 px-6 pt-3">
        {TABS.map((item) => (
          <button
            key={item.id}
            onClick={() => setTab(item.id)}
            aria-current={tab === item.id ? "page" : undefined}
            className={`shrink-0 rounded-t-lg px-4 py-2 text-sm font-medium transition ${
              tab === item.id
                ? "border-b-2 border-brand-600 text-brand-700"
                : "text-ink-500 hover:text-ink-800"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="p-6">
        {tab === "resume" && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="space-y-4">
              <TextArea
                label="About"
                value={employee.profile.about}
                disabled={!editable}
                onChange={(value) => patch("profile.about", value)}
              />
              <TextArea
                label="What I love about my job"
                value={employee.profile.what_i_love_about_my_job}
                disabled={!editable}
                onChange={(value) => patch("profile.what_i_love_about_my_job", value)}
              />
              <TextArea
                label="Interests and hobbies"
                value={employee.profile.interests_and_hobbies}
                disabled={!editable}
                onChange={(value) => patch("profile.interests_and_hobbies", value)}
              />
            </div>
            <div className="space-y-4">
              <TagList
                label="Skills"
                items={employee.profile.skills}
                disabled={!editable}
                onChange={(items) => patch("profile.skills", items)}
              />
              <TagList
                label="Certifications"
                items={employee.profile.certifications}
                disabled={!editable}
                onChange={(items) => patch("profile.certifications", items)}
              />
            </div>
          </div>
        )}

        {tab === "private" && (
          <div className="grid grid-cols-1 gap-x-8 gap-y-4 lg:grid-cols-2">
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-ink-900">Personal</h3>
              <Field label="Date of birth" name="dob" type="date"
                value={employee.profile.date_of_birth ?? ""}
                onChange={(v) => patch("profile.date_of_birth", v || null)}
                errors={profileErrors.date_of_birth} />
              <Field label="Residing address" name="address"
                value={employee.profile.residing_address}
                onChange={(v) => patch("profile.residing_address", v)}
                errors={profileErrors.residing_address} />
              <Field label="Nationality" name="nationality"
                value={employee.profile.nationality}
                onChange={(v) => patch("profile.nationality", v)}
                errors={profileErrors.nationality} />
              <Field label="Personal email" name="personal_email" type="email"
                value={employee.profile.personal_email}
                onChange={(v) => patch("profile.personal_email", v)}
                errors={profileErrors.personal_email} />
            </div>

            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-ink-900">Bank details</h3>
              <p className="-mt-2 text-xs text-ink-500">
                Encrypted at rest — stored as ciphertext, never as readable text.
              </p>
              <Field label="Bank name" name="bank_name"
                value={employee.bank_detail.bank_name}
                onChange={(v) => patch("bank_detail.bank_name", v)}
                errors={bankErrors.bank_name} />
              <Field label="Account number" name="account_number"
                value={employee.bank_detail.account_number}
                onChange={(v) => patch("bank_detail.account_number", v)}
                errors={bankErrors.account_number} />
              <Field label="IFSC code" name="ifsc_code"
                value={employee.bank_detail.ifsc_code}
                onChange={(v) => patch("bank_detail.ifsc_code", v)}
                errors={bankErrors.ifsc_code} />
              <Field label="PAN number" name="pan_number"
                value={employee.bank_detail.pan_number}
                onChange={(v) => patch("bank_detail.pan_number", v)}
                errors={bankErrors.pan_number} />
              <Field label="UAN number" name="uan_number"
                value={employee.bank_detail.uan_number}
                onChange={(v) => patch("bank_detail.uan_number", v)}
                errors={bankErrors.uan_number} />
            </div>
          </div>
        )}

        {tab === "salary" && <SalaryInfo userId={userId} editable={viewer?.role === "admin"} />}
        {tab === "security" && <SecurityTab />}

        {editable && tab !== "salary" && tab !== "security" && (
          <div className="mt-6 flex items-center gap-3 border-t border-ink-100 pt-5">
            <button
              onClick={save}
              disabled={saving}
              className="rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white
                hover:bg-brand-700 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
            {saved && <span className="text-sm text-green-700">Saved.</span>}
            {error && <span className="text-sm text-red-600">{error.message}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

function TextArea({
  label, value, onChange, disabled,
}: {
  label: string; value: string; onChange: (v: string) => void; disabled?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-ink-700">{label}</label>
      <textarea
        rows={4}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-ink-300 px-3 py-2 text-sm outline-none transition
          focus:border-brand-500 focus:ring-2 focus:ring-brand-200 disabled:bg-ink-50 disabled:text-ink-600"
      />
    </div>
  );
}

function TagList({
  label, items, onChange, disabled,
}: {
  label: string; items: string[]; onChange: (items: string[]) => void; disabled?: boolean;
}) {
  const [draft, setDraft] = useState("");

  function add() {
    const value = draft.trim();
    if (!value || items.includes(value)) return;
    onChange([...items, value]);
    setDraft("");
  }

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-ink-700">{label}</label>
      <div className="flex flex-wrap gap-2">
        {items.length === 0 && <p className="text-sm text-ink-400">None added.</p>}
        {items.map((item) => (
          <span
            key={item}
            className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1 text-sm text-brand-700"
          >
            {item}
            {!disabled && (
              <button
                onClick={() => onChange(items.filter((existing) => existing !== item))}
                aria-label={`Remove ${item}`}
                className="text-brand-400 hover:text-brand-700"
              >
                ×
              </button>
            )}
          </span>
        ))}
      </div>
      {!disabled && (
        <div className="flex gap-2">
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                add();
              }
            }}
            placeholder={`Add ${label.toLowerCase().replace(/s$/, "")}…`}
            className="flex-1 rounded-lg border border-ink-300 px-3 py-2 text-sm outline-none
              focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
          />
          <button
            onClick={add}
            className="rounded-lg border border-ink-300 px-3 py-2 text-sm font-medium text-ink-700 hover:bg-ink-50"
          >
            Add
          </button>
        </div>
      )}
    </div>
  );
}
