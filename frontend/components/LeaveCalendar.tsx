"use client";

import { useMemo, useState } from "react";

type Request = {
  id: number;
  start_date: string;
  end_date: string;
  type_name: string;
  status: "to_approve" | "approved" | "refused";
  employee_name: string;
};

const STATUS_CLASS: Record<Request["status"], string> = {
  approved: "bg-brand-600 text-white",
  to_approve: "bg-amber-200 text-amber-900",
  refused: "bg-red-100 text-red-500 line-through",
};

const STATUS_LABEL: Record<Request["status"], string> = {
  approved: "Validated",
  to_approve: "To approve",
  refused: "Refused",
};

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const WEEKDAY_INITIALS = ["S", "M", "T", "W", "T", "F", "S"];

function toKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
    date.getDate(),
  ).padStart(2, "0")}`;
}

/** A year at a glance, with each leave day shaded by the status of its request.
    Mirrors the calendar in the specification's Time Off view. */
export function LeaveCalendar({ requests }: { requests: Request[] }) {
  const [year, setYear] = useState(() => new Date().getFullYear());

  // One lookup from date key to the request covering it, so rendering stays cheap.
  const byDate = useMemo(() => {
    const map = new Map<string, Request>();
    for (const request of requests) {
      const cursor = new Date(request.start_date);
      const end = new Date(request.end_date);
      while (cursor <= end) {
        map.set(toKey(cursor), request);
        cursor.setDate(cursor.getDate() + 1);
      }
    }
    return map;
  }, [requests]);

  const today = toKey(new Date());

  return (
    <section className="rounded-xl border border-ink-200 bg-white p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-semibold text-ink-900">Leave calendar</h2>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setYear((current) => current - 1)}
            aria-label="Previous year"
            className="rounded-lg border border-ink-300 px-2 py-1 text-sm text-ink-600 hover:bg-ink-50"
          >
            ←
          </button>
          <span className="min-w-[3.5rem] text-center text-sm font-medium text-ink-900">
            {year}
          </span>
          <button
            onClick={() => setYear((current) => current + 1)}
            aria-label="Next year"
            className="rounded-lg border border-ink-300 px-2 py-1 text-sm text-ink-600 hover:bg-ink-50"
          >
            →
          </button>
        </div>

        <ul className="ml-auto flex flex-wrap items-center gap-3 text-xs text-ink-600">
          {(Object.keys(STATUS_LABEL) as Request["status"][]).map((status) => (
            <li key={status} className="flex items-center gap-1.5">
              <span className={`h-3 w-3 rounded ${STATUS_CLASS[status].split(" ")[0]}`} />
              {STATUS_LABEL[status]}
            </li>
          ))}
        </ul>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {MONTHS.map((monthName, monthIndex) => {
          const firstWeekday = new Date(year, monthIndex, 1).getDay();
          const dayCount = new Date(year, monthIndex + 1, 0).getDate();

          return (
            <div key={monthName}>
              <p className="mb-1.5 text-xs font-semibold text-ink-700">{monthName}</p>
              <div className="grid grid-cols-7 gap-0.5 text-center">
                {WEEKDAY_INITIALS.map((initial, index) => (
                  <span key={index} className="py-0.5 text-[10px] font-medium text-ink-400">
                    {initial}
                  </span>
                ))}

                {/* Blank cells so the first day lands on the right weekday. */}
                {Array.from({ length: firstWeekday }, (_, index) => (
                  <span key={`pad-${index}`} />
                ))}

                {Array.from({ length: dayCount }, (_, index) => {
                  const day = index + 1;
                  const key = `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                  const request = byDate.get(key);
                  const isToday = key === today;

                  return (
                    <span
                      key={day}
                      title={
                        request
                          ? `${request.type_name} — ${STATUS_LABEL[request.status]}`
                          : undefined
                      }
                      className={`rounded py-0.5 text-[11px] leading-5 ${
                        request ? STATUS_CLASS[request.status] : "text-ink-600"
                      } ${isToday && !request ? "ring-1 ring-brand-400" : ""}`}
                    >
                      {day}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
