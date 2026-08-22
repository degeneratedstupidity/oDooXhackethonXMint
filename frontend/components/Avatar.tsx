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

  // A stable colour per person, so a directory of initials circles reads as a set of
  // distinct people rather than one repeated tile. Derived from the name, so it does not
  // change between renders or between the grid and the profile page.
  const palette = [
    "bg-violet-100 text-violet-700",
    "bg-sky-100 text-sky-700",
    "bg-emerald-100 text-emerald-700",
    "bg-amber-100 text-amber-700",
    "bg-rose-100 text-rose-700",
    "bg-teal-100 text-teal-700",
    "bg-indigo-100 text-indigo-700",
  ];
  const hash = Array.from(name).reduce((total, char) => total + char.charCodeAt(0), 0);
  const tint = palette[hash % palette.length];

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
      className={`${dimensions} ${tint} flex shrink-0 items-center justify-center rounded-full font-semibold`}
    >
      {initials || "?"}
    </div>
  );
}
