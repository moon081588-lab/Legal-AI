/** Build an .ics calendar file for legal deadlines.
 *
 *  Deadlines only help if they reach the person. Exporting to their phone
 *  calendar needs no server, no account, and no notification infrastructure —
 *  and leaks nothing about the case beyond what they choose to save.
 */

export type CalendarItem = {
  title: string;
  date: Date;
  description?: string;
};

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function toDateStamp(d: Date): string {
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}`;
}

function toStamp(d: Date): string {
  return `${toDateStamp(d)}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}Z`;
}

function escape(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
}

/** Fold lines at 75 octets as required by RFC 5545. */
function fold(line: string): string {
  if (line.length <= 75) return line;
  const parts: string[] = [];
  let rest = line;
  while (rest.length > 75) {
    parts.push(rest.slice(0, 75));
    rest = " " + rest.slice(75);
  }
  parts.push(rest);
  return parts.join("\r\n");
}

export function buildIcs(items: CalendarItem[]): string {
  const now = new Date();
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Legal-AI//KR//",
    "CALSCALE:GREGORIAN",
  ];

  items.forEach((item, i) => {
    const end = new Date(item.date);
    end.setUTCDate(end.getUTCDate() + 1);
    lines.push(
      "BEGIN:VEVENT",
      `UID:legal-ai-${now.getTime()}-${i}@localhost`,
      `DTSTAMP:${toStamp(now)}`,
      `DTSTART;VALUE=DATE:${toDateStamp(item.date)}`,
      `DTEND;VALUE=DATE:${toDateStamp(end)}`,
      fold(`SUMMARY:${escape(item.title)}`),
      fold(`DESCRIPTION:${escape(item.description ?? "")}`),
      // Remind a day ahead — a deadline you learn about on the day is too late.
      "BEGIN:VALARM",
      "TRIGGER:-P1D",
      "ACTION:DISPLAY",
      fold(`DESCRIPTION:${escape(item.title)}`),
      "END:VALARM",
      "END:VEVENT"
    );
  });

  lines.push("END:VCALENDAR");
  return lines.join("\r\n");
}

export function downloadIcs(items: CalendarItem[], filename = "법률기한.ics"): void {
  const blob = new Blob([buildIcs(items)], { type: "text/calendar;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
