import { describe, expect, it } from "vitest";
import {
  displayValue,
  formatBytes,
  formatClock,
  formatDurationMs,
  formatIST,
  formatISTDate,
  formatISTTime,
  formatPercent,
  parseTime,
  shortHash,
  sigmoid,
} from "./format";

describe("IST formatting", () => {
  it("formats a UTC timestamp as DD/MM/YYYY HH:mm:ss in Asia/Kolkata (+05:30)", () => {
    expect(formatIST("2026-11-07T17:49:10.911034Z")).toBe("07/11/2026 23:19:10");
  });

  it("rolls the date over at midnight IST", () => {
    expect(formatIST("2026-11-07T18:30:00Z")).toBe("08/11/2026 00:00:00");
    expect(formatISTDate("2026-11-07T18:30:00Z")).toBe("08/11/2026");
    expect(formatISTTime("2026-11-07T18:30:05Z")).toBe("00:00:05");
  });

  it("treats naive timestamps as UTC and accepts +00:00 offsets", () => {
    expect(formatIST("2026-01-01T00:00:00")).toBe("01/01/2026 05:30:00");
    expect(formatIST("2026-01-01T00:00:00+00:00")).toBe("01/01/2026 05:30:00");
  });

  it("uses a 24-hour clock", () => {
    expect(formatIST("2026-03-15T10:15:30Z")).toBe("15/03/2026 15:45:30");
  });

  it("returns an em dash for missing or invalid input", () => {
    expect(formatIST(null)).toBe("—");
    expect(formatIST(undefined)).toBe("—");
    expect(formatIST("not a date")).toBe("—");
    expect(parseTime("")).toBeNull();
  });

  it("trims microseconds instead of failing", () => {
    expect(parseTime("2026-11-07T17:49:10.911034Z")?.toISOString()).toBe("2026-11-07T17:49:10.911Z");
  });
});

describe("sizes, durations and hashes", () => {
  it("formats bytes", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1023)).toBe("1023 B");
    expect(formatBytes(50225)).toBe("49.0 KB");
    expect(formatBytes(3262912)).toBe("3.11 MB");
    expect(formatBytes(null)).toBe("—");
    expect(formatBytes(-1)).toBe("—");
  });

  it("formats media clock time", () => {
    expect(formatClock(0)).toBe("0:00");
    expect(formatClock(9.96)).toBe("0:09");
    expect(formatClock(65)).toBe("1:05");
    expect(formatClock(3723)).toBe("1:02:03");
    expect(formatClock(Number.NaN)).toBe("—");
  });

  it("formats technique durations", () => {
    expect(formatDurationMs(0.1)).toBe("0.1 ms");
    expect(formatDurationMs(84.9)).toBe("85 ms");
    expect(formatDurationMs(4307.7)).toBe("4.31 s");
    expect(formatDurationMs(30500)).toBe("30.5 s");
    expect(formatDurationMs(125000)).toBe("2 min 05 s");
    expect(formatDurationMs(undefined)).toBe("—");
  });

  it("shortens hashes keeping both ends", () => {
    const h = "36eb38b41b1034407c00a773afd5453ce83f0dadbd6181d8a342f9f972b0b4e6";
    expect(shortHash(h)).toBe("36eb38b4…b0b4e6");
    expect(shortHash(h, 4, 4)).toBe("36eb…b4e6");
    expect(shortHash("abc")).toBe("abc");
    expect(shortHash(null)).toBe("—");
  });

  it("formats percentages and values", () => {
    expect(formatPercent(0.999, 1)).toBe("99.9%");
    expect(formatPercent(null)).toBe("—");
    expect(displayValue(true)).toBe("yes");
    expect(displayValue(null)).toBe("—");
    expect(displayValue({ a: 1 })).toBe('{"a":1}');
    expect(displayValue("x".repeat(200), 10)).toBe(`${"x".repeat(10)}…`);
  });

  it("maps logits to probabilities", () => {
    expect(sigmoid(0)).toBe(0.5);
    expect(sigmoid(-3.864)).toBeCloseTo(0.0205, 3);
  });
});
