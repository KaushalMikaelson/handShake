/**
 * The ONE place rupees exist.
 *
 * Everything server-side - catalog, policy engine, Razorpay order - is integer
 * paise. Converting anywhere else would reintroduce exactly the 100x bug the
 * paise-everywhere decision exists to prevent, so this module is the only
 * boundary where the conversion happens.
 */
export function formatINR(paise: number | null | undefined): string {
  if (paise === null || paise === undefined) return "—";
  const rupees = paise / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: rupees % 1 === 0 ? 0 : 2,
  }).format(rupees);
}

export function formatTime(iso: string): string {
  if (!iso) return "—";
  // Timestamps from UTC (e.g. SQLite naive ISO strings) might omit timezone designators.
  // Without a timezone suffix, JS Date constructor interprets the string as local time.
  const normalized =
    iso.endsWith("Z") || /[+-]\d{2}(?::?\d{2})?$/.test(iso) ? iso : iso + "Z";
  const d = new Date(normalized);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function percent(part: number, whole: number): number {
  if (!whole) return 0;
  return Math.min(100, Math.round((part / whole) * 100));
}
