"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Avatar } from "@/components/Avatar";
import { StatusDot } from "@/components/StatusDot";
import type { WorkStatus } from "@/components/StatusDot";
import { NewEmployeeDialog } from "@/components/NewEmployeeDialog";
import { LoadError } from "@/components/LoadError";
import { apiFetch } from "@/lib/api";
import type { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { CurrentUser } from "@/lib/auth";

type DirectoryEntry = CurrentUser & { work_status: WorkStatus };

export default function EmployeesPage() {
  const { user } = useAuth();
  const [employees, setEmployees] = useState<DirectoryEntry[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const load = useCallback(async (term: string) => {
    setLoading(true);
    setError(null);
    try {
      const query = term ? `?search=${encodeURIComponent(term)}` : "";
      setEmployees(await apiFetch<DirectoryEntry[]>(`/employees/${query}`));
    } catch (caught) {
      setError((caught as ApiError).message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced so typing in the search box doesn't fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => load(search.trim()), 250);
    return () => clearTimeout(timer);
  }, [search, load]);

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        {user?.role !== "employee" && (
          <button
            onClick={() => setDialogOpen(true)}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-700"
          >
            New
          </button>
        )}
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by name, login ID, role or department…"
          aria-label="Search employees"
          className="min-w-0 flex-1 rounded-lg border border-ink-300 bg-white px-3.5 py-2 text-sm outline-none
            transition placeholder:text-ink-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
        />
      </div>

      {error ? (
        <LoadError message={error} onRetry={() => load(search.trim())} />
      ) : loading ? (
        <p className="py-16 text-center text-sm text-ink-500">Loading employees…</p>
      ) : employees.length === 0 ? (
        <div className="rounded-xl border border-dashed border-ink-300 py-16 text-center">
          <p className="text-sm font-medium text-ink-700">No employees found</p>
          <p className="mt-1 text-sm text-ink-500">
            {search ? "Try a different search term." : "Add your first team member to get started."}
          </p>
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {employees.map((employee) => (
            <li key={employee.id}>
              <Link
                href={`/employees/${employee.id}`}
                className="flex items-center gap-3 rounded-xl border border-ink-200 bg-white p-4 transition
                  hover:border-brand-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-brand-400"
              >
                <Avatar name={employee.full_name} src={employee.avatar} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink-900">
                    {employee.full_name}
                  </p>
                  <p className="truncate text-xs text-ink-500">
                    {employee.job_position || "—"}
                  </p>
                  <p className="truncate text-xs text-ink-400">{employee.login_id}</p>
                </div>
                <StatusDot status={employee.work_status} />
              </Link>
            </li>
          ))}
        </ul>
      )}

      {dialogOpen && (
        <NewEmployeeDialog
          onClose={() => setDialogOpen(false)}
          onCreated={() => {
            setDialogOpen(false);
            load(search.trim());
          }}
        />
      )}
    </AppShell>
  );
}
