/** Shared TaxMate mark: gradient tile, 8-point star, check. */
import { useId } from "react";

export default function TaxMateMark({
  size = 56,
  title,
}: {
  size?: number;
  title?: string;
}) {
  const gid = `tm-${useId().replace(/:/g, "")}`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <defs>
        <linearGradient id={`${gid}-g`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7C5CFF" />
          <stop offset="1" stopColor="#3B6CF6" />
        </linearGradient>
        <clipPath id={`${gid}-c`}>
          <rect width="64" height="64" rx="14" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${gid}-c)`}>
        <rect width="64" height="64" fill={`url(#${gid}-g)`} />
        <g fill="#fff" transform="translate(32 32)">
          <rect x="-12" y="-12" width="24" height="24" />
          <rect x="-12" y="-12" width="24" height="24" transform="rotate(45)" />
        </g>
        <path
          d="M24 33.2l5.4 5.4 11.2-12.2"
          fill="none"
          stroke="#6B4CFF"
          strokeWidth="5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </g>
    </svg>
  );
}
