/** Durable local storage for the evidence journal.
 *
 *  For a stalking victim documenting months of incidents, this data may be the
 *  only copy that exists. localStorage is fragile (small quota, cleared by
 *  browser cleanup, throws when full), so entries live in IndexedDB with a
 *  one-time migration from the old localStorage key, plus encrypted
 *  backup/restore the user controls.
 */

export type Entry = {
  id: string;
  date: string;
  time: string;
  title: string;
  desc: string;
  photos: string[];
};

const DB_NAME = "legal_ai";
const DB_VERSION = 1;
const STORE = "journal";
const LEGACY_KEY = "legal_ai_journal";
const MIGRATED_FLAG = "legal_ai_journal_migrated";

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "id" });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return openDB().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const store = db.transaction(STORE, mode).objectStore(STORE);
        const req = fn(store);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      })
  );
}

function sortEntries(entries: Entry[]): Entry[] {
  return [...entries].sort((a, b) => (a.date + a.time < b.date + b.time ? 1 : -1));
}

/** Reads all entries, migrating any legacy localStorage data on first run.
 *  Falls back to localStorage entirely if IndexedDB is unavailable
 *  (private mode in some browsers). */
export async function loadEntries(): Promise<Entry[]> {
  try {
    await migrateLegacy();
    const all = await tx<Entry[]>("readonly", (s) => s.getAll() as IDBRequest<Entry[]>);
    return sortEntries(all);
  } catch {
    try {
      return sortEntries(JSON.parse(localStorage.getItem(LEGACY_KEY) ?? "[]"));
    } catch {
      return [];
    }
  }
}

async function migrateLegacy(): Promise<void> {
  if (localStorage.getItem(MIGRATED_FLAG)) return;
  let legacy: Entry[] = [];
  try {
    legacy = JSON.parse(localStorage.getItem(LEGACY_KEY) ?? "[]");
  } catch {
    legacy = [];
  }
  for (const e of legacy) await tx("readwrite", (s) => s.put(e));
  localStorage.setItem(MIGRATED_FLAG, "1");
  // Keep the legacy copy as a safety net; it is small and may be the only backup.
}

export async function saveEntry(entry: Entry): Promise<void> {
  try {
    await tx("readwrite", (s) => s.put(entry));
  } catch {
    const all = sortEntries([entry, ...(await loadEntries())]);
    localStorage.setItem(LEGACY_KEY, JSON.stringify(all));
  }
}

export async function deleteEntry(id: string): Promise<void> {
  try {
    await tx("readwrite", (s) => s.delete(id));
  } catch {
    const all = (await loadEntries()).filter((e) => e.id !== id);
    localStorage.setItem(LEGACY_KEY, JSON.stringify(all));
  }
}

/* ---------------- backup / restore ---------------- */

const MAGIC = "LEGALAI-JOURNAL-V1";

/** Encrypt with AES-GCM from a passphrase (PBKDF2). Empty passphrase = plain JSON. */
export async function exportBackup(entries: Entry[], passphrase: string): Promise<Blob> {
  const payload = JSON.stringify({ magic: MAGIC, exported: new Date().toISOString(), entries });
  if (!passphrase) return new Blob([payload], { type: "application/json" });

  const enc = new TextEncoder();
  const salt = bytes(16);
  const iv = bytes(12);
  const key = await deriveKey(passphrase, toBuffer(salt));
  const cipher = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: toBuffer(iv) },
    key,
    enc.encode(payload)
  );
  const body = {
    magic: MAGIC,
    encrypted: true,
    salt: b64(salt),
    iv: b64(iv),
    data: b64(new Uint8Array(cipher)),
  };
  return new Blob([JSON.stringify(body)], { type: "application/json" });
}

export async function importBackup(text: string, passphrase: string): Promise<Entry[]> {
  const parsed = JSON.parse(text);
  if (parsed.magic !== MAGIC) throw new Error("이 파일은 증거 일지 백업 파일이 아닙니다.");
  if (!parsed.encrypted) return parsed.entries as Entry[];

  const key = await deriveKey(passphrase, toBuffer(unb64(parsed.salt)));
  try {
    const plain = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: toBuffer(unb64(parsed.iv)) },
      key,
      toBuffer(unb64(parsed.data))
    );
    return JSON.parse(new TextDecoder().decode(plain)).entries as Entry[];
  } catch {
    throw new Error("복원에 실패했습니다. 암호를 확인해 주세요.");
  }
}

async function deriveKey(passphrase: string, salt: ArrayBuffer): Promise<CryptoKey> {
  const enc = new TextEncoder();
  const base = await crypto.subtle.importKey("raw", enc.encode(passphrase), "PBKDF2", false, [
    "deriveKey",
  ]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: 150_000, hash: "SHA-256" },
    base,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

function bytes(n: number): Uint8Array {
  return crypto.getRandomValues(new Uint8Array(n));
}

function toBuffer(u8: Uint8Array): ArrayBuffer {
  return u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.byteLength) as ArrayBuffer;
}

function b64(u8: Uint8Array): string {
  let s = "";
  for (let i = 0; i < u8.length; i++) s += String.fromCharCode(u8[i]);
  return btoa(s);
}

function unb64(s: string): Uint8Array {
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
}

/** Suggest a backup every 5 entries, and whenever 14 days have passed. */
export function shouldPromptBackup(count: number): boolean {
  if (count === 0) return false;
  const last = Number(localStorage.getItem("legal_ai_last_backup") ?? 0);
  const stale = Date.now() - last > 14 * 24 * 3600 * 1000;
  return (count % 5 === 0 && last === 0) || stale;
}

export function markBackedUp(): void {
  localStorage.setItem("legal_ai_last_backup", String(Date.now()));
}
