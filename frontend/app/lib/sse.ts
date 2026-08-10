/** Incremental SSE decoder. Feed raw chunks; get complete {event, data} pairs.
 *  Extracted from the page component so it can be unit-tested against
 *  malformed chunk boundaries, split multibyte characters, etc. */

export type SSEEvent = { event: string; data: string };

export class SSEDecoder {
  private buffer = "";
  private decoder = new TextDecoder();

  /** Feed a raw byte chunk; returns complete events parsed so far. */
  feed(chunk: Uint8Array): SSEEvent[] {
    this.buffer += this.decoder.decode(chunk, { stream: true });
    return this.drain();
  }

  /** Call at stream end to flush any trailing block. */
  end(): SSEEvent[] {
    this.buffer += this.decoder.decode();
    const events = this.drain();
    if (this.buffer.trim()) {
      const last = parseBlock(this.buffer);
      this.buffer = "";
      if (last) events.push(last);
    }
    return events;
  }

  private drain(): SSEEvent[] {
    const blocks = this.buffer.split("\n\n");
    this.buffer = blocks.pop() ?? "";
    const events: SSEEvent[] = [];
    for (const block of blocks) {
      const parsed = parseBlock(block);
      if (parsed) events.push(parsed);
    }
    return events;
  }
}

export function parseBlock(block: string): SSEEvent | null {
  let event = "";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7).trim();
    else if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data: ")) dataLines.push(line.slice(6));
    else if (line.startsWith("data:")) dataLines.push(line.slice(5));
  }
  if (!event) return null;
  return { event, data: dataLines.join("\n") };
}
