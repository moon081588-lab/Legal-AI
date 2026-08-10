"use client";

import { useEffect, useState } from "react";

type Entry = {
  id: string;
  date: string;
  time: string;
  title: string;
  desc: string;
  photos: string[]; // data URLs
};

const STORAGE_KEY = "legal_ai_journal";

function quickExit() {
  window.location.replace("https://weather.naver.com");
}

export default function Journal() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);

  useEffect(() => {
    try {
      setEntries(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]"));
    } catch {
      setEntries([]);
    }
  }, []);

  function persist(next: Entry[]) {
    setEntries(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      alert("저장 공간이 부족합니다. 사진 수를 줄이거나 오래된 항목을 내보낸 뒤 삭제해 주세요.");
    }
  }

  function addPhotos(files: FileList | null) {
    if (!files) return;
    Array.from(files).slice(0, 3 - photos.length).forEach((f) => {
      const reader = new FileReader();
      reader.onload = () => setPhotos((p) => [...p, reader.result as string].slice(0, 3));
      reader.readAsDataURL(f);
    });
  }

  function addEntry() {
    if (!date || (!title.trim() && !desc.trim())) return;
    const entry: Entry = {
      id: String(Date.now()),
      date, time, title: title.trim(), desc: desc.trim(), photos,
    };
    persist([entry, ...entries].sort((a, b) => (a.date + a.time < b.date + b.time ? 1 : -1)));
    setDate(""); setTime(""); setTitle(""); setDesc(""); setPhotos([]);
  }

  function removeEntry(id: string) {
    if (confirm("이 기록을 삭제할까요?")) persist(entries.filter((e) => e.id !== id));
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
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "증거일지.md";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="container journal">
      <button className="quick-exit" onClick={quickExit} title="이 페이지를 즉시 벗어납니다">
        ✕ 빠른 나가기
      </button>

      <div className="header">
        <div className="header-row">
          <h1>📔 증거 일지</h1>
          <div style={{ display: "flex", gap: 8 }}>
            <a className="settings-btn" href="/">← 채팅으로</a>
            {entries.length > 0 && (
              <>
                <button className="settings-btn" onClick={exportMarkdown}>⬇ 내보내기(.md)</button>
                <button className="settings-btn" onClick={() => window.print()}>🖨 인쇄(사진 포함)</button>
              </>
            )}
          </div>
        </div>
        <div className="notice">
          일지는 <b>이 기기의 브라우저에만</b> 저장되며 서버로 전송되지 않습니다. 스토킹·협박처럼 반복되는
          피해는 발생할 때마다 기록해 두면 패턴을 입증하는 중요한 자료가 됩니다. 날짜가 지난 뒤에도
          기억나는 대로 기록해 두세요.
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
            <img key={i} src={p} alt="첨부" className="thumb" onClick={() => setPhotos(photos.filter((_, j) => j !== i))} title="누르면 제거" />
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
