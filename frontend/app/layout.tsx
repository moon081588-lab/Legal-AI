import "./globals.css";

export const metadata = {
  title: "Legal-AI — 생활법령 AI 도우미",
  description: "대한민국 법령 정보를 쉽게 안내하는 AI 서비스 (법률 자문 아님)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
