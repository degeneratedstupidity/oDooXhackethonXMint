"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { LeaveCalendar } from "@/components/LeaveCalendar";
import { NewTimeOffDialog } from "@/components/NewTimeOffDialog";
import { LoadError } from "@/components/LoadError";
import { apiFetch } from "@/lib/api";
import type { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Request = {
  id: number;
  employee_name: string;
  login_id: string;
  type_name: string;
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  attachment: string | null;
  status: "to_approve" | "approved" | "refused";
};

type Balance = {
  type: number;
  name: string;
  is_paid: boolean;
  allowance: number | null;
  used: number;
  available: number | null;
};

const STATUS_STYLES: Record<Request["status"], string> = {
  to_approve: "bg-amber-100 text-amber-800",
  approved: "bg-green-100 text-green-800",
  refused: "bg-red-100 text-red-700",
};

const STATUS_LABELS: Record<Request["status"], string> = {
  to_approve: "To Approve",
  approved: "Approved",
  refused: "Refused",
};

export default function TimeOffPage() {
  const { user } = useAuth();
  const manages = user?.role !== "employee";

  const [requests, setRequests] = useState<Request[]>([]);
  const [balances, setBalances] = useState<Balance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [acting, setActing] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [requestList, balanceList] = await Promise.all([
        apiFetch<Request[]>("/time-off/"),
        apiFetch<Balance[]>("/time-off/balances/"),
      ]);
      setRequests(requestList);
      setBalances(balanceList);
    } catch (caught) {
      setError((caught as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function review(id: number, decision: "approve" | "refuse") {
    setActing(id);
    try {
      await apiFetch(`/time-off/${id}/${decision}/`, { method: "POST" });
      await load();
    } finally {
      setActing(null);
    }
  }

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-semibold text-ink-900">Time Off</h1>
        <button
          onClick={() => setDialogOpen(true)}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-700"
        >
          New
        </button>
      </div>

      {/* The employee's own remaining balance, per type. */}
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {balances.map((balance) => (
          <div key={balance.type} className="rounded-xl border border-ink-200 bg-white p-4">
            <p className="text-sm font-medium text-brand-700">{balance.name}</p>
            {balance.available === null ? (
              <p className="mt-1 text-sm text-ink-500">No annual limit</p>
            ) : (
              <p className="mt-1 text-sm text-ink-600">
                <strong className="text-xl font-semibold text-ink-900">
                  {balance.available}
                </strong>{" "}
                of {balance.allowance} days available
              </p>
            )}
          </div>
        ))}
      </div>

      {error && <LoadError message={error} onRetry={load} />}

      {!loading && requests.length > 0 && (
        <div className="mb-6">
          <LeaveCalendar requests={requests} />
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-ink-200 bg-white">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-ink-200 text-left text-xs uppercase tracking-wide text-ink-500">
              {manages && <th className="px-4 py-3 font-medium">Name</th>}
              <th className="px-4 py-3 font-medium">Start Date</th>
              <th className="px-4 py-3 font-medium">End Date</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Reason</th>
              {manages && <th className="px-4 py-3 font-medium">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-ink-500">
                  Loading…
                </td>
              </tr>
            ) : requests.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-ink-500">
                  No time off requests yet.
                </td>
              </tr>
            ) : (
              requests.map((request) => (
                <tr key={request.id} className="border-b border-ink-100 last:border-0">
                  {manages && (
                    <td className="px-4 py-3">
                      <span className="font-medium text-ink-900">{request.employee_name}</span>
                    </td>
                  )}
                  <td className="px-4 py-3 text-ink-700">
                    {new Date(request.start_date).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-ink-700">
                    {new Date(request.end_date).toLocaleDateString()}
                    <span className="ml-1.5 text-xs text-ink-400">({request.days}d)</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-brand-700">{request.type_name}</span>
                    {request.attachment && (
                      <a
                        href={request.attachment}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-2 inline-flex items-center gap-1 rounded bg-ink-100 px-1.5 py-0.5
                          text-xs text-ink-600 hover:bg-ink-200 hover:text-ink-900"
                        title="Open the supporting document"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                          strokeLinecap="round" strokeLinejoin="round" className="h-3 w-3" aria-hidden>
                          <path d="M21.4 11.05l-9.19 9.19a5 5 0 01-7.07-7.07l9.19-9.19a3.33 3.33 0 014.71 4.71l-9.2 9.19a1.67 1.67 0 01-2.35-2.36l8.49-8.48" />
                        </svg>
                        Document
                      </a>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[request.status]}`}
                    >
                      {STATUS_LABELS[request.status]}
                    </span>
                  </td>
                  <td className="max-w-[16rem] truncate px-4 py-3 text-ink-600" title={request.reason}>
                    {request.reason || <span className="text-ink-400">—</span>}
                  </td>
                  {manages && (
                    <td className="px-4 py-3">
                      {request.status === "to_approve" ? (
                        <div className="flex gap-1.5">
                          <button
                            onClick={() => review(request.id, "refuse")}
                            disabled={acting === request.id}
                            className="rounded-md bg-red-100 px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-200 disabled:opacity-50"
                          >
                            Refuse
                          </button>
                          <button
                            onClick={() => review(request.id, "approve")}
                            disabled={acting === request.id}
                            className="rounded-md bg-green-100 px-2.5 py-1 text-xs font-medium text-green-800 hover:bg-green-200 disabled:opacity-50"
                          >
                            Approve
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-ink-400">Reviewed</span>
                      )}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {dialogOpen && (
        <NewTimeOffDialog
          onClose={() => setDialogOpen(false)}
          onCreated={() => {
            setDialogOpen(false);
            load();
          }}
        />
      )}
    </AppShell>
  );
}
