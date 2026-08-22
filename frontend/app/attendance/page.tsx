"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { LoadError } from "@/components/LoadError";
import { apiFetch } from "@/lib/api";
import type { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Row = {
  id: number;
  employee_name: string;
  login_id: string;
  date: string;
  check_in: string;
  check_out: string | null;
  attended_hours: number;
  break_hours: string;
  work_hours: number;
  extra_hours: number;
};

const time = (iso: string | null) =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";

function shiftMonth(month: string, delta: number) {
  const [year, monthNumber] = month.split("-").map(Number);
  const date = new Date(year, monthNumber - 1 + delta, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function shiftDay(day: string, delta: number) {
  const date = new Date(day);
  date.setDate(date.getDate() + delta);
  return date.toISOString().slice(0, 10);
}

/** Admin and HR see everyone for a chosen day; employees see their own month.
    That split comes straight from the wireframes. */
export default function AttendancePage() {
  const { user } = useAuth();
  const manages = user?.role !== "employee";

  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const query = manages ? `?date=${day}` : `?month=${month}`;
      setRows(await apiFetch<Row[]>(`/attendance/${query}`));
    } catch (caught) {
      setError((caught as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, [manages, day, month]);

  useEffect(() => {
    load();
  }, [load]);

  const totalHours = rows.reduce((sum, row) => sum + row.work_hours, 0);

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-semibold text-ink-900">Attendance</h1>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => (manages ? setDay(shiftDay(day, -1)) : setMonth(shiftMonth(month, -1)))}
            aria-label="Previous"
            className="rounded-lg border border-ink-300 bg-white px-2.5 py-1.5 text-sm text-ink-600 hover:bg-ink-50"
          >
            ←
          </button>
          <button
            onClick={() => (manages ? setDay(shiftDay(day, 1)) : setMonth(shiftMonth(month, 1)))}
            aria-label="Next"
            className="rounded-lg border border-ink-300 bg-white px-2.5 py-1.5 text-sm text-ink-600 hover:bg-ink-50"
          >
            →
          </button>
          <input
            type={manages ? "date" : "month"}
            value={manages ? day : month}
            onChange={(event) => (manages ? setDay(event.target.value) : setMonth(event.target.value))}
            aria-label={manages ? "Date" : "Month"}
            className="rounded-lg border border-ink-300 bg-white px-3 py-1.5 text-sm outline-none
              focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
          />
        </div>

        {!manages && (
          <div className="ml-auto flex gap-2 text-sm">
            <span className="rounded-lg bg-white px-3 py-1.5 text-ink-600 ring-1 ring-ink-200">
              Days present <strong className="text-ink-900">{rows.length}</strong>
            </span>
            <span className="rounded-lg bg-white px-3 py-1.5 text-ink-600 ring-1 ring-ink-200">
              Hours <strong className="text-ink-900">{totalHours.toFixed(2)}</strong>
            </span>
          </div>
        )}
      </div>

      {error && <LoadError message={error} onRetry={load} />}

      <div className="overflow-x-auto rounded-xl border border-ink-200 bg-white">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-ink-200 text-left text-xs uppercase tracking-wide text-ink-500">
              <th className="px-4 py-3 font-medium">{manages ? "Employee" : "Date"}</th>
              <th className="px-4 py-3 font-medium">Check In</th>
              <th className="px-4 py-3 font-medium">Check Out</th>
              <th className="px-4 py-3 font-medium">Break</th>
              <th className="px-4 py-3 font-medium">Work Hours</th>
              <th className="px-4 py-3 font-medium">Extra Hours</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-ink-500">
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-ink-500">
                  No attendance recorded for this {manages ? "day" : "month"}.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id} className="border-b border-ink-100 last:border-0">
                  <td className="px-4 py-3">
                    {manages ? (
                      <>
                        <span className="font-medium text-ink-900">{row.employee_name}</span>
                        <span className="ml-2 text-xs text-ink-400">{row.login_id}</span>
                      </>
                    ) : (
                      new Date(row.date).toLocaleDateString()
                    )}
                  </td>
                  <td className="px-4 py-3 text-ink-700">{time(row.check_in)}</td>
                  <td className="px-4 py-3 text-ink-700">{time(row.check_out)}</td>
                  <td className="px-4 py-3 text-ink-500">{Number(row.break_hours).toFixed(2)}</td>
                  <td
                    className="px-4 py-3 text-ink-700"
                    title={`${row.attended_hours.toFixed(2)} h on site less ${Number(row.break_hours).toFixed(2)} h break`}
                  >
                    {row.work_hours.toFixed(2)}
                  </td>
                  <td className="px-4 py-3">
                    {row.extra_hours > 0 ? (
                      <span className="font-medium text-green-700">
                        +{row.extra_hours.toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-ink-400">—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
