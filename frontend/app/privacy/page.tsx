"use client";

/** 개인정보 처리방침.
 *  앱 스토어 심사와 공개 서비스에 필수이며, 무엇보다 이용자가 안심하고 쓸 수
 *  있어야 하므로 "무엇을 저장하지 않는지"를 먼저 밝힙니다. */

function quickExit() {
  window.location.replace("https://weather.naver.com");
}

export default function Privacy() {
  return (
    <div className="container">
      <button className="quick-exit" onClick={quickExit} title="이 페이지를 즉시 벗어납니다">
        ✕ 빠른 나가기
      </button>

      <div className="header">
        <div className="header-row">
          <h1>개인정보 처리방침</h1>
          <a className="settings-btn" href="/">← 돌아가기</a>
        </div>
        <div className="notice">
          최종 수정일: 2026-08-11 · Legal-AI는 이용자를 식별할 수 있는 정보를 수집하지 않습니다.
        </div>
      </div>

      <div className="journal-list">
        <div className="journal-entry">
          <div className="entry-head"><b>1. 수집하지 않는 정보</b></div>
          <p>
            계정, 이름, 이메일, 전화번호, 주소, 생년월일 등 이용자를 식별할 수 있는 정보를 일절
            수집하지 않습니다. 회원가입 절차가 없습니다. 광고 식별자나 추적 쿠키를 사용하지 않으며,
            제3자 분석 도구를 탑재하지 않습니다.
          </p>
        </div>

        <div className="journal-entry">
          <div className="entry-head"><b>2. 대화 내용</b></div>
          <p>
            이용자가 입력한 질문은 답변 생성을 위해 처리되며 <b>서버에 저장되지 않습니다</b>.
            서버 기록에는 응답 소요 시간과 참조한 조문 수만 남고, 질문 내용은 기록되지 않습니다.
          </p>
          <p>
            답변 생성 기능을 사용하는 경우, 질문과 검색된 법령 조문이 답변 생성을 위해 Anthropic의
            API로 전송됩니다. 이용자가 직접 API 키를 입력한 경우 그 키는 이용자의 브라우저에만
            저장되며 서버에 전송·보관되지 않습니다.
          </p>
        </div>

        <div className="journal-entry">
          <div className="entry-head"><b>3. 증거 일지</b></div>
          <p>
            증거 일지에 작성한 기록과 첨부한 사진은 <b>이용자 기기의 브라우저 저장소(IndexedDB)에만</b>{" "}
            저장되며 서버로 전송되지 않습니다. 따라서 운영자는 그 내용을 열람할 수 없고, 기기를
            분실하거나 브라우저 데이터를 삭제하면 복구해 드릴 수 없습니다. 백업 기능을 이용해 주세요.
          </p>
        </div>

        <div className="journal-entry">
          <div className="entry-head"><b>4. 이용자가 직접 보내는 정보</b></div>
          <p>
            답변에 대해 <b>👎(도움이 되지 않았습니다)</b>를 누르시면, 서비스 개선을 위해 해당
            <b> 질문 문장</b>과 이용자가 적어 주신 의견이 저장됩니다. 이는 이용자의 명시적인 행동이
            있을 때만 저장되며, 답변 내용이나 다른 대화는 저장되지 않습니다. 개인을 식별할 수 있는
            내용을 질문에 적으신 경우 함께 저장될 수 있으므로, 이름·연락처 등은 적지 않으실 것을
            권합니다.
          </p>
          <p>
            화면에 오류가 발생하면 오류 메시지와 발생 위치가 기록됩니다. 이용자가 입력한 내용은
            포함되지 않습니다.
          </p>
        </div>

        <div className="journal-entry">
          <div className="entry-head"><b>5. 보관 기간과 파기</b></div>
          <p>
            서버에 저장되는 개인정보가 없으므로 별도의 보관·파기 절차가 없습니다. 위 4항의 피드백
            기록은 서비스 개선 목적을 달성한 후 지체 없이 삭제합니다.
          </p>
        </div>

        <div className="journal-entry">
          <div className="entry-head"><b>6. 이용자의 권리</b></div>
          <p>
            기기에 저장된 정보(증거 일지, 설정)는 이용자가 언제든지 앱에서 직접 삭제하거나 브라우저
            데이터를 지워 삭제할 수 있습니다. 그 밖의 문의는 아래 연락처로 보내 주세요.
          </p>
        </div>

        <div className="journal-entry">
          <div className="entry-head"><b>7. 서비스의 성격</b></div>
          <p>
            본 서비스는 법령 정보를 안내하는 도구이며 법률 자문을 제공하지 않습니다. 모든 답변은
            AI가 생성한 것으로 표시됩니다. 구체적인 사안은 변호사 또는 대한법률구조공단(국번없이
            132) 상담을 이용해 주세요.
          </p>
        </div>

        <div className="journal-entry">
          <div className="entry-head"><b>8. 문의</b></div>
          <p>
            개인정보 관련 문의: <a href="mailto:moon081588@gmail.com">moon081588@gmail.com</a>
            <br />
            소스 코드:{" "}
            <a href="https://github.com/moon081588-lab/Legal-AI" target="_blank" rel="noreferrer">
              github.com/moon081588-lab/Legal-AI
            </a>{" "}
            (모든 처리 과정을 직접 확인하실 수 있습니다)
          </p>
        </div>

        <div className="journal-entry">
          <div className="entry-head"><b>Privacy Policy (English summary)</b></div>
          <p>
            Legal-AI collects no personally identifiable information and has no user accounts. Your
            questions are processed to generate an answer but are <b>not stored on the server</b>;
            server logs contain only timing data. If you use answer generation, your question and the
            retrieved statutes are sent to Anthropic&apos;s API for processing. Evidence journal
            entries and photos are stored <b>only on your device</b> and never transmitted. Only when
            you explicitly press 👎 is your question text saved, to improve the service. No tracking
            cookies, no advertising identifiers, no third-party analytics. This service provides legal
            information, not legal advice. Contact: moon081588@gmail.com
          </p>
        </div>
      </div>
    </div>
  );
}
