"use client";

import { useEffect, useState } from "react";
import { Field } from "./Field";
import { apiFetch } from "@/lib/api";
import type { ApiError } from "@/lib/api";

type LeaveType = {
  id: number;
  name: string;
  requires_attachment: boolean;
};

export function NewTimeOffDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [typeId, setTypeId] = useState<string>("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    apiFetch<LeaveType[]>("/time-off-types/").then((list) => {
      setTypes(list);
      if (list.length) setTypeId(String(list[0].id));
    });
  }, []);

  const selected = types.find((type) => String(type.id) === typeId);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    // Multipart because sick leave can carry a certificate.
    const payload = new FormData();
    payload.append("type", typeId);
    payload.append("start_date", startDate);
    payload.append("end_date", endDate);
    payload.append("reason", reason);
    if (attachment) payload.append("attachment", attachment);

    try {
      await apiFetch("/time-off/", { method: "POST", body: payload });
      onCreated();
    } catch (caught) {
      setError(caught as ApiError);
    } finally {
      setSubmitting(false);
    }
  }

  const fieldErrors = error?.fields ?? {};

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="time-off-title"
    >
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
        noValidate
      >
        <h2 id="time-off-title" className="text-lg font-semibold text-ink-900">
          Time off request
        </h2>

        <div className="mt-5 space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="type" className="block text-sm font-medium text-ink-700">
              Time off type<span className="ml-0.5 text-brand-600">*</span>
            </label>
            <select
              id="type"
              value={typeId}
              onChange={(event) => setTypeId(event.target.value)}
              className="w-full rounded-lg border border-ink-300 px-3 py-2.5 text-sm outline-none
                transition focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
            >
              {types.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name}
                </option>
              ))}
            </select>
            {fieldErrors.type && <p className="text-xs text-red-600">{fieldErrors.type[0]}</p>}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field
              label="From"
              name="start_date"
              type="date"
              value={startDate}
              onChange={setStartDate}
              errors={fieldErrors.start_date}
              required
            />
            <Field
              label="To"
              name="end_date"
              type="date"
              value={endDate}
              onChange={setEndDate}
              errors={fieldErrors.end_date}
              required
            />
          </div>

          <Field
            label="Reason"
            name="reason"
            value={reason}
            onChange={setReason}
            errors={fieldErrors.reason}
            placeholder="Optional"
          />

          {selected?.requires_attachment && (
            <div className="space-y-1.5">
              <label htmlFor="attachment" className="block text-sm font-medium text-ink-700">
                Supporting document<span className="ml-0.5 text-brand-600">*</span>
              </label>
              <input
                id="attachment"
                type="file"
                onChange={(event) => setAttachment(event.target.files?.[0] ?? null)}
                className="w-full rounded-lg border border-ink-300 px-3 py-2 text-sm
                  file:mr-3 file:rounded file:border-0 file:bg-brand-50 file:px-3 file:py-1.5
                  file:text-sm file:font-medium file:text-brand-700"
              />
              <p className="text-xs text-ink-500">Required for {selected.name}.</p>
              {fieldErrors.attachment && (
                <p className="text-xs text-red-600">{fieldErrors.attachment[0]}</p>
              )}
            </div>
          )}

          {error && !Object.keys(fieldErrors).length && (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error.message}
            </p>
          )}
          {fieldErrors.non_field_errors && (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {fieldErrors.non_field_errors[0]}
            </p>
          )}
        </div>

        <div className="mt-6 flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-lg border border-ink-300 px-4 py-2.5 text-sm font-medium text-ink-700 hover:bg-ink-50"
          >
            Discard
          </button>
          <button
            type="submit"
            disabled={submitting || !startDate || !endDate}
            className="flex-1 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white
              hover:bg-brand-700 disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Submit"}
          </button>
        </div>
      </form>
    </div>
  );
}
