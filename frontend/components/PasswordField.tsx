"use client";

import { useState } from "react";

/** Password input with the show/hide toggle from the wireframes. */
export function PasswordField({
  label,
  name,
  value,
  onChange,
  errors,
  required,
  autoComplete,
}: {
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  errors?: string[];
  required?: boolean;
  autoComplete?: string;
}) {
  const [visible, setVisible] = useState(false);
  const invalid = Boolean(errors?.length);

  return (
    <div className="space-y-1.5">
      <label htmlFor={name} className="block text-sm font-medium text-ink-700">
        {label}
        {required && <span className="ml-0.5 text-brand-600">*</span>}
      </label>
      <div className="relative">
        <input
          id={name}
          name={name}
          type={visible ? "text" : "password"}
          value={value}
          required={required}
          autoComplete={autoComplete}
          aria-invalid={invalid}
          aria-describedby={invalid ? `${name}-error` : undefined}
          onChange={(event) => onChange(event.target.value)}
          className={`w-full rounded-lg border px-3 py-2.5 pr-11 text-sm outline-none transition
            focus:ring-2 focus:ring-brand-200
            ${
              invalid
                ? "border-red-400 focus:border-red-500 focus:ring-red-100"
                : "border-ink-300 focus:border-brand-500"
            }`}
        />
        <button
          type="button"
          onClick={() => setVisible((current) => !current)}
          aria-label={visible ? "Hide password" : "Show password"}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-ink-400 hover:text-ink-600"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
            strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden>
            {visible ? (
              <>
                <path d="M3 3l18 18" />
                <path d="M10.6 10.6a2 2 0 002.8 2.8" />
                <path d="M9.4 5.2A9.7 9.7 0 0112 5c5 0 9 5 9 7a12 12 0 01-2.4 3.2M6.2 6.9C3.9 8.5 3 11 3 12c0 2 4 7 9 7a9.6 9.6 0 004-.9" />
              </>
            ) : (
              <>
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
                <circle cx="12" cy="12" r="2.5" />
              </>
            )}
          </svg>
        </button>
      </div>
      {invalid && (
        <p id={`${name}-error`} className="text-xs text-red-600">
          {errors!.join(" ")}
        </p>
      )}
    </div>
  );
}
