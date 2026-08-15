// 后端 API 客户端
// 后端地址：默认 localhost:8000，部署时用 NEXT_PUBLIC_API_BASE 环境变量覆盖
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type ApiJob = {
  岗位名称?: string;
  城市?: string;
  岗位描述?: string;
  任职资格?: string;
  招聘类型?: string;
  需求人数?: number;
  当前状态?: string;
  [key: string]: unknown;
};

export type ApiResult = {
  候选人?: string;
  岗位名称?: string;
  匹配度?: number;
  等级?: string;
  风险等级?: string;
  匹配总结?: string;
  推荐结论?: string;
};

export type ApiQuestion = {
  id: string;
  维度: string;
  问题: string;
  类型: "单选" | "文本";
  选项?: string[];
};

export async function fetchJobs(): Promise<ApiJob[]> {
  const r = await fetch(`${API_BASE}/jobs`);
  const d = await r.json();
  return d.jobs || [];
}

export async function fetchResults(): Promise<ApiResult[]> {
  const r = await fetch(`${API_BASE}/results`);
  const d = await r.json();
  return d.results || [];
}

export async function fetchInterviewQuestions(candidate: string): Promise<{ questions?: ApiQuestion[]; job?: string }> {
  const r = await fetch(`${API_BASE}/interview/questions?candidate=${encodeURIComponent(candidate)}`);
  return r.json();
}

export async function submitInterview(candidate: string, job: string, answers: Record<string, string>) {
  const r = await fetch(`${API_BASE}/interview/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate, job, answers }),
  });
  return r.json();
}
