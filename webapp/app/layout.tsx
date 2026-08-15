import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hisense HireAI · 海信招聘运营智能体",
  description: "面向制造业招聘场景的岗位治理、人才匹配、AI 初筛与招聘运营智能体。",
  openGraph: {
    title: "海信招聘运营智能体",
    description: "岗位治理 · 人才匹配 · AI初筛 · 人工终审",
    images: ["/og.jpg"],
  },
  twitter: {
    card: "summary_large_image",
    title: "海信招聘运营智能体",
    description: "岗位治理 · 人才匹配 · AI初筛 · 人工终审",
    images: ["/og.jpg"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
