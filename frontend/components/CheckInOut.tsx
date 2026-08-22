"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { ApiError } from "@/lib/api";

export type AttendanceRecord = {
  id: number;
  date: string;
  check_in: string;
  check_out: string | null;
  work_hours: number;
  extra_hours: number;
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** The check in / check out control from the wireframes. Shows "Since HH:MM" once the
    employee is checked in, and reports today's total once they check out. */
export function CheckInOut({ onChange }: { onChange?: () => void }) {
  const [record, setRecord] = useState<AttendanceRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRecord(await apiFetch<AttendanceRecord | null>("/attendance/today/"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function act(endpoint: "check_in" | "check_out") {
    setBusy(true);
    setError(null);
    try {
      setRecord(await apiFetch<AttendanceRecord>(`/attendance/${endpoint}/`, { method: "POST" }));
      onChange?.();
    } catch (caught) {
      setError((caught as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return null;

  const checkedIn = record && !record.check_out;
  const done = record?.check_out;

  return (
    <div className="flex flex-col items-end gap-1">
      {done ? (
        <div className="rounded-lg bg-ink-100 px-3 py-1.5 text-right">
          <p className="text-xs font-medium text-ink-700">
            {record.work_hours.toFixed(2)} h today
          </p>
          <p className="text-[11px] text-ink-500">
            {formatTime(record.check_in)} – {formatTime(record.check_out!)}
          </p>
        </div>
      ) : (
        <button
          onClick={() => act(checkedIn ? "check_out" : "check_in")}
          disabled={busy}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:opacity-50 ${
            checkedIn
              ? "bg-red-50 text-red-700 hover:bg-red-100"
              : "bg-status-present/10 text-green-700 hover:bg-status-present/20"
          }`}
        >
          {busy ? "…" : checkedIn ? "Check Out →" : "Check In →"}
        </button>
      )}

      {checkedIn && (
        <p className="text-[11px] text-ink-500">Since {formatTime(record.check_in)}</p>
      )}
      {error && <p className="text-[11px] text-red-600">{error}</p>}
    </div>
  );
}
