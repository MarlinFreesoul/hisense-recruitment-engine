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

export async function fetchInterviewQuestions(candidate: string, assessment = ""): Promise<{ questions?: ApiQuestion[]; job?: string }> {
  const url = `${API_BASE}/interview/questions?candidate=${encodeURIComponent(candidate)}` +
    (assessment ? `&assessment=${encodeURIComponent(assessment)}` : "");
  const r = await fetch(url);
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

// ===================== 模块 1：上传即打分 =====================
export type ApiTalentRow = {
  candidateId: string;
  name: string;
  jobFamily: string;
  jobName: string;
  totalScore: number;
  grade: string;
  riskLevel: string;
  tags: string[];
  status: string;
  summary: string;
};

export async function fetchTalentPool(jobFamily = ""): Promise<ApiTalentRow[]> {
  const url = `${API_BASE}/talent-pool${jobFamily ? `?job_family=${encodeURIComponent(jobFamily)}` : ""}`;
  const r = await fetch(url);
  const d = await r.json();
  return d.comparison || [];
}

export async function seedDemo(): Promise<{ seeded: number; pooled: number }> {
  const r = await fetch(`${API_BASE}/demo/seed`, { method: "POST" });
  return r.json();
}

export async function offerFallback(jobFamily: string, rejectedId: string) {
  const r = await fetch(`${API_BASE}/decision/offer-fallback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_family: jobFamily, rejected_id: rejectedId }),
  });
  return r.json();
}

export async function generateJd(jobFamily: string, params: Record<string, unknown> = {}) {
  const r = await fetch(`${API_BASE}/jd/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_family: jobFamily, params }),
  });
  return r.json();
}

export async function saveJd(jobFamily: string, params: Record<string, unknown> = {}) {
  const r = await fetch(`${API_BASE}/jd/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_family: jobFamily, params }),
  });
  return r.json();
}

export async function screenResume(text: string, jobName: string, jobFamily: string) {
  const r = await fetch(`${API_BASE}/screen`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, job_name: jobName, job_family: jobFamily, write_feishu: false }),
  });
  return r.json();
}

// 真实简历文件上传即打分（PDF/TXT/MD）→ 自动入人才池（内存，演示安全）
export async function uploadResume(file: File, jobName: string, jobFamily: string) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("job_name", jobName);
  fd.append("job_family", jobFamily);
  fd.append("write_feishu", "false");
  const r = await fetch(`${API_BASE}/screen/upload`, { method: "POST", body: fd });
  return r.json();
}

// HR 将候选人推送给用人部门复核（双向回环起点）
export async function departmentPush(payload: { candidate_id: string; name: string; job_family: string }) {
  const r = await fetch(`${API_BASE}/review/department-push`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return r.json();
}

export async function submitDepartmentDecision(payload: {
  candidate_id: string; name: string; job_family: string; decision: string; note: string;
}) {
  const r = await fetch(`${API_BASE}/review/department-decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return r.json();
}

export async function fetchDecisions(): Promise<Array<Record<string, unknown>>> {
  const r = await fetch(`${API_BASE}/review/decisions`);
  const d = await r.json();
  return d.decisions || [];
}

// ===================== 模块 6：视频面试闭环 =====================
// 后端视频端点详见后端 api/server.py（独立 TRTC + 独立 ASR + 云端录制 → 文件识别 → 评分 → 写飞书）

export type VideoRoomSide = { user_id: string; user_sig: string };
export type VideoRoomResp = {
  success: boolean;
  room_id?: number;
  sdk_app_id?: number;
  candidate?: VideoRoomSide;
  interviewer?: VideoRoomSide;
  candidate_id?: string;
  eligible?: boolean;
  reason?: string;
  error?: string;
  missing?: string[];
};

// 候选人填写 / 修改资料（飞书简历库字段），返回唯一候选人 ID（record_id）
export async function videoRegister(fields: Record<string, unknown>, recordId = ""): Promise<{
  success: boolean; candidate_id?: string; eligible?: boolean; missing?: string[]; reason?: string; error?: string;
}> {
  const r = await fetch(`${API_BASE}/video/candidate/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ record_id: recordId, fields }),
  });
  return r.json();
}

// 只读查询候选人档案与面试资格（前端据此决定是否展示「资料登记」表单）
export async function videoCandidateGet(candidateId: string): Promise<{
  success: boolean; exists?: boolean; candidate_id?: string; name?: string;
  eligible?: boolean; reason?: string; missing?: string[];
}> {
  const r = await fetch(`${API_BASE}/video/candidate/${encodeURIComponent(candidateId)}`);
  return r.json();
}

// 创建 TRTC 视频房间（含资格门禁 + 双方 UserSig）
export async function videoRoom(candidate: string, interviewer = "hr", roomId?: number): Promise<VideoRoomResp> {
  const r = await fetch(`${API_BASE}/video/room`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate, interviewer, room_id: roomId ?? null }),
  });
  return r.json();
}

// 签出腾讯云实时 ASR 的 WebSocket 连接串（SecretKey 不下发浏览器）
export async function videoAsr(voiceId: string): Promise<{ success: boolean; url?: string; error?: string }> {
  const r = await fetch(`${API_BASE}/video/asr?voice_id=${encodeURIComponent(voiceId)}`);
  return r.json();
}

// HR 实时辅助：基于累计转写返回建议追问 / 风险预警 / STAR 提示
export async function videoAssist(transcript: string, familyKey = "firstline"): Promise<{
  success: boolean; assist?: { 建议追问?: string; 风险预警?: string; STAR提示?: string }; error?: string;
}> {
  const r = await fetch(`${API_BASE}/video/assist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript, family_key: familyKey }),
  });
  return r.json();
}

// 启动 TRTC 云端录制（默认 TRTC_RECORD_ENABLED=true 才会成功）
export async function videoRecordingStart(roomId: number, candidate: string): Promise<{
  success: boolean; task_id?: string; error?: string;
}> {
  const r = await fetch(`${API_BASE}/video/recording/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ room_id: roomId, candidate }),
  });
  return r.json();
}

// 停止云端录制（文件落 COS）
export async function videoRecordingStop(taskId: string): Promise<{ success: boolean; error?: string }> {
  const r = await fetch(`${API_BASE}/video/recording/stop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId }),
  });
  return r.json();
}

// 录制后处理：发现文件 → 文件识别(带说话人分离) → interviewEvaluation → 写飞书
export async function videoRecordingProcess(payload: {
  room_id?: number; candidate?: string; candidate_id?: string; family_key?: string;
  hr_user_id?: string; candidate_user_id?: string; track_mode?: string; write_feishu?: boolean;
}): Promise<{ success: boolean; evaluation?: Record<string, unknown>; error?: string }> {
  const r = await fetch(`${API_BASE}/video/recording/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ family_key: "firstline", track_mode: "separate", write_feishu: true, ...payload }),
  });
  return r.json();
}

// 兜底：用带说话人标签的双人转写（或无录制源时的本地转写）直接生成评价并写飞书
export async function videoReport(payload: {
  candidate?: string; job?: string; candidate_id?: string; family_key?: string;
  speaker_transcript?: Array<{ speaker: string; text: string }>; recording_url?: string;
}): Promise<{ success: boolean; evaluation?: Record<string, unknown>; error?: string }> {
  const r = await fetch(`${API_BASE}/video/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ family_key: "firstline", ...payload }),
  });
  return r.json();
}
