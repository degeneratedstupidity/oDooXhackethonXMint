"use client";

/** Profile picture, falling back to initials when no avatar is uploaded. */
export function Avatar({
  name,
  src,
  size = "md",
}: {
  name: string;
  src?: string | null;
  size?: "sm" | "md" | "lg";
}) {
  const dimensions = {
    sm: "h-8 w-8 text-xs",
    md: "h-12 w-12 text-sm",
    lg: "h-24 w-24 text-2xl",
  }[size];

  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  if (src) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={src}
        alt={name}
        className={`${dimensions} shrink-0 rounded-full object-cover`}
      />
    );
  }

  return (
    <div
      aria-hidden
      className={`${dimensions} flex shrink-0 items-center justify-center rounded-full bg-brand-100 font-semibold text-brand-700`}
    >
      {initials || "?"}
    </div>
  );
}
