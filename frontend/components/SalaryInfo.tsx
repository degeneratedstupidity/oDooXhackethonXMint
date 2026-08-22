"use client";

import { useCallback, useEffect, useState } from "react";
import { PayslipPanel } from "./PayslipPanel";
import { apiFetch } from "@/lib/api";
import type { ApiError } from "@/lib/api";
import type { SalaryStructure } from "@/lib/types";

const money = (value: string | number) =>
  `₹${Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/** The Salary Info tab. Rendered only for administrators — the API refuses everyone
    else, so this is presentation, not the access control itself. */
export function SalaryInfo({ userId, editable }: { userId: number; editable: boolean }) {
  const [structure, setStructure] = useState<SalaryStructure | null>(null);
  const [wage, setWage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const all = await apiFetch<SalaryStructure[]>(`/salary/?user=${userId}`);
      const mine = all.find((item) => item.user === userId) ?? null;
      setStructure(mine);
      if (mine) setWage(mine.monthly_wage);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  async function saveWage() {
    if (!structure) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await apiFetch<SalaryStructure>(`/salary/${structure.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ monthly_wage: wage }),
      });
      setStructure(updated);
      setWage(updated.monthly_wage);
    } catch (caught) {
      const apiError = caught as ApiError;
      setError(apiError.fields.non_field_errors?.[0] ?? apiError.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="py-8 text-sm text-ink-500">Loading salary…</p>;
  if (!structure) return <p className="py-8 text-sm text-ink-500">No salary structure found.</p>;

  const total = structure.components.reduce((sum, c) => sum + Number(c.amount), 0);

  return (
    <div className="space-y-8">
      <section className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div className="space-y-4">
          <div>
            <label htmlFor="wage" className="block text-sm font-medium text-ink-700">
              Monthly wage
            </label>
            <div className="mt-1.5 flex gap-2">
              <input
                id="wage"
                type="number"
                min="0"
                step="0.01"
                value={wage}
                disabled={!editable}
                onChange={(event) => setWage(event.target.value)}
                className="w-full rounded-lg border border-ink-300 px-3 py-2 text-sm outline-none
                  transition focus:border-brand-500 focus:ring-2 focus:ring-brand-200 disabled:bg-ink-50"
              />
              {editable && (
                <button
                  onClick={saveWage}
                  disabled={saving || wage === structure.monthly_wage}
                  className="shrink-0 rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white
                    hover:bg-brand-700 disabled:opacity-40"
                >
                  {saving ? "…" : "Save"}
                </button>
              )}
            </div>
            <p className="mt-1 text-xs text-ink-500">
              Components recalculate automatically when the wage changes.
            </p>
          </div>

          <div className="rounded-lg bg-ink-50 px-3 py-2.5">
            <p className="text-xs text-ink-500">Yearly wage</p>
            <p className="text-lg font-semibold text-ink-900">{money(structure.yearly_wage)}</p>
          </div>
        </div>

        <dl className="space-y-2 text-sm">
          <div className="flex justify-between border-b border-ink-100 pb-2">
            <dt className="text-ink-500">Working days per week</dt>
            <dd className="font-medium text-ink-900">{structure.working_days_per_week}</dd>
          </div>
          <div className="flex justify-between border-b border-ink-100 pb-2">
            <dt className="text-ink-500">Break time</dt>
            <dd className="font-medium text-ink-900">{structure.break_time_hours} hrs</dd>
          </div>
          <div className="flex justify-between border-b border-ink-100 pb-2">
            <dt className="text-ink-500">Professional tax</dt>
            <dd className="font-medium text-ink-900">{money(structure.professional_tax)} / month</dd>
          </div>
        </dl>
      </section>

      {error && (
        <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <section>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Salary components</h3>
        <div className="overflow-x-auto rounded-xl border border-ink-200">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-ink-200 bg-ink-50 text-left text-xs uppercase tracking-wide text-ink-500">
                <th className="px-4 py-2.5 font-medium">Component</th>
                <th className="px-4 py-2.5 font-medium">Basis</th>
                <th className="px-4 py-2.5 text-right font-medium">Amount / month</th>
              </tr>
            </thead>
            <tbody>
              {structure.components.map((component) => (
                <tr key={component.id} className="border-b border-ink-100 last:border-0">
                  <td className="px-4 py-2.5 font-medium text-ink-800">{component.label}</td>
                  <td className="px-4 py-2.5 text-xs text-ink-500">
                    {component.computation_type === "percent_of_wage" && `${component.value}% of wage`}
                    {component.computation_type === "percent_of_basic" && `${component.value}% of basic`}
                    {component.computation_type === "fixed_amount" && "Fixed amount"}
                    {component.computation_type === "remainder" && "Remainder of wage"}
                  </td>
                  <td className="px-4 py-2.5 text-right font-medium text-ink-900">
                    {money(component.amount)}
                  </td>
                </tr>
              ))}
              <tr className="bg-ink-50 font-semibold">
                <td className="px-4 py-2.5 text-ink-900" colSpan={2}>
                  Total
                </td>
                <td className="px-4 py-2.5 text-right text-ink-900">{money(total)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3 className="mb-3 text-sm font-semibold text-ink-900">Provident fund</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-ink-200 p-3">
            <p className="text-xs text-ink-500">Employee ({structure.pf_employee_percent}%)</p>
            <p className="mt-0.5 font-semibold text-ink-900">{money(structure.pf_employee_amount)}</p>
          </div>
          <div className="rounded-lg border border-ink-200 p-3">
            <p className="text-xs text-ink-500">Employer ({structure.pf_employer_percent}%)</p>
            <p className="mt-0.5 font-semibold text-ink-900">{money(structure.pf_employer_amount)}</p>
          </div>
        </div>
        <p className="mt-2 text-xs text-ink-500">Calculated on basic salary.</p>
      </section>

      <PayslipPanel userId={userId} />
    </div>
  );
}
