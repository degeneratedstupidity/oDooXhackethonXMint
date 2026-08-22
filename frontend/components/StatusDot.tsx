"use client";

export type WorkStatus = "present" | "absent" | "leave";

const PRESENTATION: Record<WorkStatus, { label: string; className: string; icon?: string }> = {
  present: { label: "In the office", className: "bg-status-present" },
  leave: { label: "On leave", className: "", icon: "✈️" },
  absent: { label: "Absent", className: "bg-status-absent" },
};

/** The attendance indicator on each directory card: green present, plane on leave,
    yellow absent. */
export function StatusDot({ status }: { status: WorkStatus }) {
  const { label, className, icon } = PRESENTATION[status];

  if (icon) {
    return (
      <span title={label} aria-label={label} role="img" className="text-sm leading-none">
        {icon}
      </span>
    );
  }

  return (
    <span
      title={label}
      aria-label={label}
      role="img"
      className={`block h-3 w-3 rounded-full ring-2 ring-white ${className}`}
    />
  );
}
