"use client";

import { useEffect, useMemo, useState } from "react";

function quickExit() {
  window.location.replace("https://weather.naver.com");
}

export default function Glossary() {
  const [terms, setTerms] = useState<Record<string, string>>({});
  const [q, setQ] = useState("");

  useEffect(() => {
    fetch("/api/glossary")
      .then((r) => r.json())
      .then(setTerms)
      .catch(() => setTerms({}));
  }, []);

  const filtered = useMemo(
    () =>
      Object.entries(terms).filter(
        ([term, def]) => !q.trim() || term.includes(q.trim()) || def.includes(q.trim())
      ),
    [terms, q]
  );

  return (
    <div className="container">
      <button className="quick-exit" onClick={quickExit} title="이 페이지를 즉시 벗어납니다">
        ✕ 빠른 나가기
      </button>

      <div className="header">
        <div className="header-row">
          <h1>📖 법률 용어 사전</h1>
          <a className="settings-btn" href="/">← 채팅으로</a>
        </div>
        <div className="notice">
          답변이나 서류에서 만나는 법률 용어를 쉬운 말로 풀어 설명합니다. 오프라인에서도 확인하실 수
          있습니다.
        </div>
        <input
          className="date-input"
          style={{ width: "100%", marginTop: 10 }}
          placeholder="용어를 검색해 보세요 (예: 불송치, 증거보전)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      <div className="journal-list">
        {filtered.length === 0 && <p className="empty">검색 결과가 없습니다.</p>}
        {filtered.map(([term, def]) => (
          <div key={term} className="journal-entry">
            <div className="entry-head"><b>{term}</b></div>
            <p>{def}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
