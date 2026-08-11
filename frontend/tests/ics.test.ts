import { describe, expect, it } from "vitest";
import { buildIcs } from "../app/lib/ics";

describe("buildIcs", () => {
  const items = [
    { title: "[법률 기한] CCTV 보존 요청", date: new Date("2026-09-10T00:00:00Z"), description: "통상 30일 내 삭제" },
  ];

  it("produces a valid calendar envelope", () => {
    const ics = buildIcs(items);
    expect(ics.startsWith("BEGIN:VCALENDAR")).toBe(true);
    expect(ics.trimEnd().endsWith("END:VCALENDAR")).toBe(true);
    expect(ics).toContain("BEGIN:VEVENT");
    expect(ics).toContain("DTSTART;VALUE=DATE:20260910");
  });

  it("includes a one-day-ahead reminder", () => {
    expect(buildIcs(items)).toContain("TRIGGER:-P1D");
  });

  it("escapes commas and semicolons in text", () => {
    const ics = buildIcs([
      { title: "기한, 중요; 확인", date: new Date("2026-09-10T00:00:00Z"), description: "설명, 내용" },
    ]);
    expect(ics).toContain("기한\\, 중요\\; 확인");
  });

  it("uses CRLF line endings as required by RFC 5545", () => {
    expect(buildIcs(items).includes("\r\n")).toBe(true);
  });

  it("handles an empty list without crashing", () => {
    const ics = buildIcs([]);
    expect(ics).toContain("BEGIN:VCALENDAR");
    expect(ics).not.toContain("BEGIN:VEVENT");
  });
});
