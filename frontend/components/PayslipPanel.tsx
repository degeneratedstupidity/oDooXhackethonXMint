"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Payslip = {
  year: number;
  month: number;
  working_days: number;
  days_present: number;
  paid_leave_days: number;
  unpaid_leave_days: number;
  unaccounted_days: number;
  payable_days: number;
  per_day_rate: string;
  gross_pay: string;
  deductions: { provident_fund: string; professional_tax: string; total: string };
  net_pay: string;
};

const money = (value: string | number) =>
  `₹${Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/** Payslip for a chosen month, derived from attendance and approved leave. */
export function PayslipPanel({ userId }: { userId: number }) {
  const now = new Date();
  const [month, setMonth] = useState(
    `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`,
  );
  const [payslip, setPayslip] = useState<Payslip | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [year, monthNumber] = month.split("-");
      setPayslip(
        await apiFetch<Payslip>(`/payslip/${userId}/?year=${year}&month=${Number(monthNumber)}`),
      );
    } finally {
      setLoading(false);
    }
  }, [userId, month]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-semibold text-ink-900">Payslip</h3>
        <input
          type="month"
          value={month}
          onChange={(event) => setMonth(event.target.value)}
          aria-label="Payslip month"
          className="rounded-lg border border-ink-300 px-3 py-1.5 text-sm outline-none
            focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
        />
      </div>

      {loading || !payslip ? (
        <p className="py-6 text-sm text-ink-500">Loading payslip…</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-ink-200 p-4">
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-500">
              Days
            </h4>
            <dl className="space-y-1.5 text-sm">
              <Row label="Working days" value={payslip.working_days} />
              <Row label="Present" value={payslip.days_present} />
              <Row label="Paid leave" value={payslip.paid_leave_days} />
              <Row label="Unpaid leave" value={payslip.unpaid_leave_days} negative />
              <Row label="Unaccounted" value={payslip.unaccounted_days} negative />
              <div className="flex justify-between border-t border-ink-200 pt-1.5 font-semibold">
                <dt className="text-ink-900">Payable days</dt>
                <dd className="text-ink-900">{payslip.payable_days}</dd>
              </div>
            </dl>
            <p className="mt-3 text-xs text-ink-500">
              Unpaid leave and days with no attendance reduce payable days.
            </p>
          </div>

          <div className="rounded-xl border border-ink-200 p-4">
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-500">
              Pay
            </h4>
            <dl className="space-y-1.5 text-sm">
              <Row label="Per-day rate" value={money(payslip.per_day_rate)} />
              <Row label="Gross pay" value={money(payslip.gross_pay)} />
              <Row label="Provident fund" value={`− ${money(payslip.deductions.provident_fund)}`} negative />
              <Row label="Professional tax" value={`− ${money(payslip.deductions.professional_tax)}`} negative />
              <div className="flex justify-between border-t border-ink-200 pt-1.5">
                <dt className="font-semibold text-ink-900">Net pay</dt>
                <dd className="text-lg font-semibold text-brand-700">{money(payslip.net_pay)}</dd>
              </div>
            </dl>
          </div>
        </div>
      )}
    </section>
  );
}

function Row({
  label,
  value,
  negative,
}: {
  label: string;
  value: string | number;
  negative?: boolean;
}) {
  return (
    <div className="flex justify-between">
      <dt className="text-ink-500">{label}</dt>
      <dd className={negative && Number(String(value).replace(/[^0-9.]/g, "")) > 0 ? "text-red-600" : "text-ink-800"}>
        {value}
      </dd>
    </div>
  );
}
