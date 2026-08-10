import { describe, expect, it } from "vitest";
import { SSEDecoder, parseBlock } from "../app/lib/sse";

const enc = new TextEncoder();

describe("parseBlock", () => {
  it("parses a normal event block", () => {
    expect(parseBlock('event: delta\ndata: {"text":"안녕"}')).toEqual({
      event: "delta",
      data: '{"text":"안녕"}',
    });
  });

  it("returns null for blocks without an event", () => {
    expect(parseBlock("data: orphan")).toBeNull();
    expect(parseBlock("")).toBeNull();
  });
});

describe("SSEDecoder", () => {
  it("parses events split across arbitrary chunk boundaries", () => {
    const raw = 'event: sources\ndata: []\n\nevent: delta\ndata: {"text":"보증금"}\n\n';
    for (let cut = 1; cut < raw.length - 1; cut++) {
      const d = new SSEDecoder();
      const events = [
        ...d.feed(enc.encode(raw.slice(0, cut))),
        ...d.feed(enc.encode(raw.slice(cut))),
        ...d.end(),
      ];
      expect(events.map((e) => e.event)).toEqual(["sources", "delta"]);
    }
  });

  it("handles multibyte Korean characters split mid-character", () => {
    const raw = enc.encode('event: delta\ndata: {"text":"임차권등기명령"}\n\n');
    // split inside a UTF-8 sequence
    for (const cut of [20, 21, 22, 23]) {
      const d = new SSEDecoder();
      const events = [...d.feed(raw.slice(0, cut)), ...d.feed(raw.slice(cut)), ...d.end()];
      expect(events).toHaveLength(1);
      expect(JSON.parse(events[0].data).text).toBe("임차권등기명령");
    }
  });

  it("flushes a trailing block without final newlines at end()", () => {
    const d = new SSEDecoder();
    d.feed(enc.encode("event: done\ndata: {}"));
    const events = d.end();
    expect(events).toEqual([{ event: "done", data: "{}" }]);
  });

  it("ignores malformed noise between events", () => {
    const d = new SSEDecoder();
    const events = [
      ...d.feed(enc.encode(":\n\ngarbage\n\nevent: delta\ndata: {\"text\":\"a\"}\n\n")),
      ...d.end(),
    ];
    expect(events.map((e) => e.event)).toEqual(["delta"]);
  });
});
