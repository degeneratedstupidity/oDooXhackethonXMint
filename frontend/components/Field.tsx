"use client";

/** A labelled input that renders server-side validation errors inline. */
export function Field({
  label,
  name,
  type = "text",
  value,
  onChange,
  errors,
  required,
  placeholder,
  autoComplete,
}: {
  label: string;
  name: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  errors?: string[];
  required?: boolean;
  placeholder?: string;
  autoComplete?: string;
}) {
  const invalid = Boolean(errors?.length);
  return (
    <div className="space-y-1.5">
      <label htmlFor={name} className="block text-sm font-medium text-ink-700">
        {label}
        {required && <span className="ml-0.5 text-brand-600">*</span>}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        value={value}
        required={required}
        placeholder={placeholder}
        autoComplete={autoComplete}
        aria-invalid={invalid}
        aria-describedby={invalid ? `${name}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
        className={`w-full rounded-lg border px-3 py-2.5 text-sm outline-none transition
          placeholder:text-ink-400
          focus:ring-2 focus:ring-brand-200
          ${
            invalid
              ? "border-red-400 focus:border-red-500 focus:ring-red-100"
              : "border-ink-300 focus:border-brand-500"
          }`}
      />
      {invalid && (
        <p id={`${name}-error`} className="text-xs text-red-600">
          {errors!.join(" ")}
        </p>
      )}
    </div>
  );
}
