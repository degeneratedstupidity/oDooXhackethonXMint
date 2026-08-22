"use client";

import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";

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
type Holiday = { id: number; name: string; date: string };

/** Statuses in the order they are listed in a day's detail panel. */
const STATUS_ORDER: Request["status"][] = ["approved", "to_approve", "refused"];

const STATUS_DOT: Record<Request["status"], string> = {
  approved: "bg-brand-600",
  to_approve: "bg-amber-400",
  refused: "bg-red-300",
};

/** Who is away on one day, grouped by where their request stands. */
function DayPanel({
  dateKey,
  requests,
  holiday,
  showNames,
}: {
  dateKey: string;
  requests: Request[];
  holiday?: Holiday;
  showNames: boolean;
}) {
  const heading = new Date(`${dateKey}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  const grouped = STATUS_ORDER.map((status) => ({
    status,
    items: requests.filter((request) => request.status === status),
  })).filter((group) => group.items.length > 0);

  return (
    <div
      role="tooltip"
      className="absolute bottom-full left-1/2 z-20 mb-1.5 w-56 -translate-x-1/2 rounded-lg
        border border-ink-200 bg-white p-2.5 text-left shadow-lg"
    >
      <p className="mb-1.5 text-[11px] font-semibold text-ink-900">{heading}</p>

      {holiday && (
        <p className="mb-1.5 rounded bg-ink-100 px-1.5 py-1 text-[11px] text-ink-700">
          {holiday.name}
        </p>
      )}

      {grouped.map((group) => (
        <div key={group.status} className="mb-1.5 last:mb-0">
          <p className="mb-0.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase
            tracking-wide text-ink-500">
            <span className={`h-2 w-2 rounded-full ${STATUS_DOT[group.status]}`} />
            {STATUS_LABEL[group.status]} ({group.items.length})
          </p>
          <ul className="space-y-0.5">
            {group.items.map((request) => (
              <li key={request.id} className="truncate text-[11px] text-ink-700">
                {showNames ? (
                  <>
                    <span className="font-medium">{request.employee_name}</span>
                    <span className="text-ink-500"> — {request.type_name}</span>
                  </>
                ) : (
                  request.type_name
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}

      {requests.length === 0 && !holiday && (
        <p className="text-[11px] text-ink-500">Nobody is away.</p>
      )}
    </div>
  );
}

export function LeaveCalendar({
  requests,
  showNames = false,
}: {
  requests: Request[];
  /** Admin and HR see who is away; an employee's calendar is only ever their own. */
  showNames?: boolean;
}) {
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  // The day whose detail panel is open. Hover sets it; a click pins it, so the panel is
  // reachable on a touch screen where there is no hover at all.
  const [openDay, setOpenDay] = useState<string | null>(null);
  const [pinnedDay, setPinnedDay] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Holiday[]>(`/public-holidays/?year=${year}`)
      .then(setHolidays)
      .catch(() => setHolidays([]));
  }, [year]);

  const holidayByDate = useMemo(
    () => new Map(holidays.map((holiday) => [holiday.date, holiday])),
    [holidays],
  );

  // One lookup from date key to every request covering it. This has to be a list: on an
  // Admin's calendar several people are routinely away on the same day, and keeping only
  // one of them would hide the rest.
  const byDate = useMemo(() => {
    const map = new Map<string, Request[]>();
    for (const request of requests) {
      const cursor = new Date(request.start_date);
      const end = new Date(request.end_date);
      while (cursor <= end) {
        const key = toKey(cursor);
        const existing = map.get(key);
        if (existing) existing.push(request);
        else map.set(key, [request]);
        cursor.setDate(cursor.getDate() + 1);
      }
    }
    return map;
  }, [requests]);

  const today = toKey(new Date());
  const activeDay = pinnedDay ?? openDay;

  /** The shade for a day covered by several requests at once.
      Someone actually being away outranks a request that is still only proposed. */
  function dominantStatus(dayRequests: Request[]): Request["status"] {
    return (
      STATUS_ORDER.find((status) => dayRequests.some((r) => r.status === status)) ??
      "to_approve"
    );
  }

  return (
    <section className="rounded-xl border border-ink-200 bg-white p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-semibold text-ink-900">Leave calendar</h2>
        <span className="text-xs text-ink-500">
          {showNames ? "Hover a day to see who is away" : "Hover a day for details"}
        </span>
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
          <li className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded bg-ink-200" />
            Public holiday
          </li>
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
                  const dayRequests = byDate.get(key);
                  const holiday = holidayByDate.get(key);
                  const isToday = key === today;
                  const hasDetail = Boolean(dayRequests || holiday);

                  // A leave request takes precedence: it is the thing being tracked here.
                  const shading = dayRequests
                    ? STATUS_CLASS[dominantStatus(dayRequests)]
                    : holiday
                      ? "bg-ink-200 text-ink-700"
                      : "text-ink-600";

                  return (
                    <span key={day} className="relative">
                      <span
                        tabIndex={hasDetail ? 0 : undefined}
                        onMouseEnter={() => hasDetail && setOpenDay(key)}
                        onMouseLeave={() => setOpenDay(null)}
                        onFocus={() => hasDetail && setOpenDay(key)}
                        onBlur={() => setOpenDay(null)}
                        onClick={() =>
                          hasDetail && setPinnedDay((current) => (current === key ? null : key))
                        }
                        className={`block rounded py-0.5 text-[11px] leading-5 ${shading} ${
                          isToday && !dayRequests && !holiday ? "ring-1 ring-brand-400" : ""
                        } ${
                          hasDetail
                            ? "cursor-pointer outline-none ring-offset-1 focus-visible:ring-2 focus-visible:ring-brand-500"
                            : ""
                        } ${activeDay === key ? "ring-2 ring-brand-500" : ""}`}
                      >
                        {day}
                      </span>

                      {/* More than one person away shows a count, so a busy day is
                          visible without having to hover over it first. */}
                      {dayRequests && dayRequests.length > 1 && (
                        <span
                          aria-hidden
                          className="pointer-events-none absolute -right-0.5 -top-0.5 flex h-3 w-3
                            items-center justify-center rounded-full bg-ink-900 text-[8px]
                            font-semibold leading-none text-white"
                        >
                          {dayRequests.length}
                        </span>
                      )}

                      {activeDay === key && hasDetail && (
                        <DayPanel
                          dateKey={key}
                          requests={dayRequests ?? []}
                          holiday={holiday}
                          showNames={showNames}
                        />
                      )}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {holidays.length > 0 && (
        <div className="mt-5 border-t border-ink-100 pt-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
            Public holidays
          </h3>
          <ul className="grid grid-cols-1 gap-x-6 gap-y-1 text-xs text-ink-600 sm:grid-cols-2 lg:grid-cols-3">
            {holidays.map((holiday) => (
              <li key={holiday.id} className="flex justify-between gap-3">
                <span className="truncate">{holiday.name}</span>
                <span className="shrink-0 text-ink-400">
                  {new Date(holiday.date).toLocaleDateString(undefined, {
                    day: "numeric",
                    month: "short",
                  })}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
