const LAKH = 100_000;
const CRORE = 10_000_000;

/** Full INR amount with en-IN (lakh/crore) grouping, e.g. ₹13,37,548.00. */
export function formatINRFull(value: number): string {
  return `₹${value.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Condensed INR for tight spaces (chart ticks, totals): ₹12,345 / ₹1.25L / ₹1.25Cr. */
export function formatINR(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= CRORE) return `${sign}₹${(abs / CRORE).toFixed(2)}Cr`;
  if (abs >= LAKH) return `${sign}₹${(abs / LAKH).toFixed(2)}L`;
  if (abs >= 1000) return `${sign}₹${(abs / 1000).toFixed(1)}k`;
  return `${sign}₹${abs.toFixed(0)}`;
}

/** value is a 0-1 fraction. */
export function formatPercent(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatSignedPercent(value: number, decimals = 1): string {
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(decimals)}%`;
}

export function formatHours(value: number): string {
  return `${value.toFixed(1)}h`;
}

/**
 * `amount_diff` carries raw float-subtraction noise (e.g. 9.09e-13) from the
 * matcher - round near-zero values to a clean "0.00" instead of scientific
 * notation, and never render more than 2 decimal places.
 */
export function formatDrift(value: number): string {
  const rounded = Math.abs(value) < 0.005 ? 0 : value;
  const sign = rounded > 0 ? "+" : rounded < 0 ? "-" : "";
  return `${sign}₹${Math.abs(rounded).toFixed(2)}`;
}

export function formatCount(value: number): string {
  return value.toLocaleString("en-IN");
}
