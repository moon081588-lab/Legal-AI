"use client";

/** Route-level error boundary: a render crash shows a recovery screen with
 *  emergency contacts instead of a blank page. */
export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="container">
      <div className="header">
        <h1>⚠️ 화면을 표시하는 중 문제가 발생했습니다</h1>
        <div className="notice">
          불편을 드려 죄송합니다. 아래 버튼으로 다시 시도해 주세요. 문제가 계속되면 페이지를 새로고침해
          주세요.
          <br />
          <br />
          급하게 도움이 필요하시다면: 경찰 <b>112</b> · 대한법률구조공단 <b>132</b> · 여성긴급전화{" "}
          <b>1366</b> · 자살예방 상담전화 <b>109</b>
        </div>
        <div className="toolbar">
          <button className="settings-btn" onClick={reset}>다시 시도</button>
          <a className="settings-btn" href="/">처음으로</a>
        </div>
        <p className="panel-note" style={{ marginTop: 12 }}>
          기술 정보: {error.message || "알 수 없는 오류"}
        </p>
      </div>
    </div>
  );
}
