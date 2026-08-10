"use client";

import { useEffect, useRef, useState } from "react";
import {
  deleteEntry,
  exportBackup,
  importBackup,
  loadEntries,
  markBackedUp,
  saveEntry,
  shouldPromptBackup,
  type Entry,
} from "../lib/journal-store";

function quickExit() {
  window.location.replace("https://weather.naver.com");
}

function download(blob: Blob, filename: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function Journal() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);
  const [showBackup, setShowBackup] = useState(false);
  const [nudge, setNudge] = useState(false);
  const [passphrase, setPassphrase] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadEntries().then((e) => {
      setEntries(e);
      setNudge(shouldPromptBackup(e.length));
    });
  }, []);

  async function refresh() {
    const e = await loadEntries();
    setEntries(e);
    setNudge(shouldPromptBackup(e.length));
  }

  function addPhotos(files: FileList | null) {
    if (!files) return;
    Array.from(files)
      .slice(0, 3 - photos.length)
      .forEach((f) => {
        const reader = new FileReader();
        reader.onload = () => setPhotos((p) => [...p, reader.result as string].slice(0, 3));
        reader.readAsDataURL(f);
      });
  }

  async function addEntry() {
    if (!date || (!title.trim() && !desc.trim())) return;
    await saveEntry({
      id: String(Date.now()),
      date, time, title: title.trim(), desc: desc.trim(), photos,
    });
    setDate(""); setTime(""); setTitle(""); setDesc(""); setPhotos([]);
    await refresh();
  }

  async function removeEntry(id: string) {
    if (!confirm("이 기록을 삭제할까요? 삭제하면 되돌릴 수 없습니다.")) return;
    await deleteEntry(id);
    await refresh();
  }

  async function doExportBackup() {
    const blob = await exportBackup(entries, passphrase);
    const suffix = passphrase ? "암호화" : "일반";
    download(blob, `증거일지-백업-${new Date().toISOString().slice(0, 10)}-${suffix}.json`);
    markBackedUp();
    setNudge(false);
    setPassphrase("");
  }

  async function doImport(file: File) {
    try {
      const restored = await importBackup(await file.text(), passphrase);
      for (const e of restored) await saveEntry(e);
      await refresh();
      alert(`${restored.length}건을 복원했습니다.`);
      setPassphrase("");
    } catch (e) {
      alert((e as Error).message);
    }
  }

  function exportMarkdown() {
    const lines = ["# 증거 일지", "", `내보낸 날짜: ${new Date().toLocaleDateString("ko-KR")}`, ""];
    [...entries].reverse().forEach((e) => {
      lines.push(`## ${e.date} ${e.time || ""} — ${e.title || "(제목 없음)"}`);
      if (e.desc) lines.push(e.desc);
      if (e.photos.length) lines.push(`(사진 ${e.photos.length}장 — 인쇄본 참조)`);
      lines.push("");
    });
    lines.push("※ 본 일지는 작성자가 직접 기록한 것입니다.");
    download(new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" }), "증거일지.md");
    markBackedUp();
    setNudge(false);
  }

  return (
    <div className="container journal">
      <button className="quick-exit" onClick={quickExit} title="이 페이지를 즉시 벗어납니다">
        ✕ 빠른 나가기
      </button>

      <div className="header">
        <div className="header-row">
          <h1>📔 증거 일지</h1>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <a className="settings-btn" href="/">← 채팅으로</a>
            <button className="settings-btn" onClick={() => setShowBackup(!showBackup)}>
              🔐 백업·복원
            </button>
            {entries.length > 0 && (
              <>
                <button className="settings-btn" onClick={exportMarkdown}>⬇ 내보내기(.md)</button>
                <button className="settings-btn" onClick={() => window.print()}>🖨 인쇄</button>
              </>
            )}
          </div>
        </div>

        {nudge && (
          <div className="backup-nudge">
            기록이 쌓였습니다. 기기를 잃어버리거나 브라우저 데이터가 지워지면 복구할 수 없으니
            지금 백업해 두시는 것을 권합니다.{" "}
            <button onClick={() => setShowBackup(true)}>백업하기</button>
          </div>
        )}

        {showBackup && (
          <div className="settings">
            <label>백업 암호 (선택) — 입력하면 백업 파일이 암호화됩니다</label>
            <input
              type="password"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              placeholder="비워 두면 암호화하지 않습니다"
            />
            <div className="row" style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="settings-btn" onClick={doExportBackup} disabled={!entries.length}>
                💾 백업 파일 저장
              </button>
              <button className="settings-btn" onClick={() => fileRef.current?.click()}>
                📥 백업 파일 복원
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="application/json"
                hidden
                onChange={(e) => e.target.files?.[0] && doImport(e.target.files[0])}
              />
            </div>
            <p>
              암호를 잊으면 복원할 수 없습니다. 백업 파일은 USB나 다른 기기 등 안전한 곳에 보관해
              주세요.
            </p>
          </div>
        )}

        <div className="notice">
          일지는 <b>이 기기에만</b> 저장되며 서버로 전송되지 않습니다. 스토킹·협박처럼 반복되는
          피해는 발생할 때마다 기록해 두면 패턴을 입증하는 중요한 자료가 됩니다.
        </div>
      </div>

      <div className="journal-form">
        <div className="row">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          <input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
        </div>
        <input placeholder="제목 (예: 퇴근길에 따라옴)" value={title} onChange={(e) => setTitle(e.target.value)} />
        <textarea
          placeholder="무슨 일이 있었는지 구체적으로 적어 주세요. 장소, 한 말, 목격자 등."
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          rows={4}
        />
        <div className="row">
          <label className="photo-btn">
            📷 사진 첨부 ({photos.length}/3)
            <input type="file" accept="image/*" multiple hidden onChange={(e) => addPhotos(e.target.files)} />
          </label>
          {photos.map((p, i) => (
            <img key={i} src={p} alt="첨부" className="thumb"
              onClick={() => setPhotos(photos.filter((_, j) => j !== i))} title="누르면 제거" />
          ))}
          <button className="add-btn" onClick={addEntry} disabled={!date || (!title.trim() && !desc.trim())}>
            기록 추가
          </button>
        </div>
      </div>

      <div className="journal-list">
        {entries.length === 0 && <p className="empty">아직 기록이 없습니다. 첫 기록을 추가해 보세요.</p>}
        {entries.map((e) => (
          <div key={e.id} className="journal-entry">
            <div className="entry-head">
              <b>{e.date} {e.time}</b> — {e.title || "(제목 없음)"}
              <button className="del" onClick={() => removeEntry(e.id)}>삭제</button>
            </div>
            {e.desc && <p>{e.desc}</p>}
            {e.photos.length > 0 && (
              <div className="entry-photos">
                {e.photos.map((p, i) => <img key={i} src={p} alt={`사진 ${i + 1}`} />)}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
