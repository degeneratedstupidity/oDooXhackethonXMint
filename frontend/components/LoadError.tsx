"use client";

/** Shown when a page's data could not be loaded, so a failed request is visible and
    recoverable rather than an empty screen. */
export function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-6 text-center">
      <p className="text-sm font-medium text-red-800">Could not load this page</p>
      <p className="mt-1 text-sm text-red-700">{message}</p>
      <button
        onClick={onRetry}
        className="mt-4 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700"
      >
        Try again
      </button>
    </div>
  );
}
