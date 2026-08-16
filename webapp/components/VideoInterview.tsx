"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  videoRegister, videoCandidateGet, videoRoom, videoAsr, videoAssist,
  videoRecordingStart, videoRecordingStop, videoRecordingProcess, videoReport,
  type VideoRoomResp,
} from "@/lib/api";

type Role = "hr" | "candidate";

type EvalDim = { dim?: string; score?: number; state?: string; evidence?: string };
type Evaluation = {
  overallRating?: number | null;
  dimensionScores?: EvalDim[];
  hiringSuggestion?: string;
  complianceFlags?: string[];
  transcriptSummary?: string;
};

type AssistTip = { 建议追问?: string; 风险预警?: string; STAR提示?: string };

// 候选人资格门禁必填字段（与后端 config.CANDIDATE_REQUIRED_FIELDS 一致，即飞书简历库字段名）
const REQUIRED_FIELDS: [string, string, string][] = [
  ["姓名", "姓名", "如：张三"],
  ["最近职位", "最近职位", "如：设备维修工程师"],
  ["最近公司", "最近公司", "如：某制造企业"],
  ["工作年限", "工作年限", "如：5"],
];

// ---- 动态加载腾讯云 TRTC Web SDK（独立接入，音视频直连腾讯云，SecretKey 不下发浏览器）----
let trtcPromise: Promise<any> | null = null;
function loadTrtc(): Promise<any> {
  if (typeof window === "undefined") return Promise.reject(new Error("非浏览器环境"));
  const w = window as any;
  if (w.TRTC) return Promise.resolve(w.TRTC);
  if (trtcPromise) return trtcPromise;
  trtcPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://web.sdk.qcloud.com/trtc/webrtc/v5/trtc.js";
    s.async = true;
    s.onload = () => (w.TRTC ? resolve(w.TRTC) : reject(new Error("TRTC 全局对象缺失")));
    s.onerror = () => reject(new Error("TRTC SDK 加载失败，请检查网络后重试"));
    document.head.appendChild(s);
  });
  return trtcPromise;
}

export default function VideoInterview() {
  // ---------- 角色与候选人 ----------
  const [role, setRole] = useState<Role>("hr");
  const [candidateId, setCandidateId] = useState("");
  const [familyKey, setFamilyKey] = useState("firstline");

  // ---------- 候选人资格门禁 / 资料登记 ----------
  const [profileName, setProfileName] = useState("");
  const [eligible, setEligible] = useState<boolean | null>(null);
  const [eligMissing, setEligMissing] = useState<string[]>([]);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [regForm, setRegForm] = useState<Record<string, string>>({ 姓名: "", 最近职位: "", 最近公司: "", 工作年限: "" });
  const [regBusy, setRegBusy] = useState(false);

  // ---------- 房间 / 录制 / 连接状态 ----------
  const [joined, setJoined] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("就绪。HR 点击「开始面试」、候选人点击「进入面试间」启动闭环。");
  const [inviteLink, setInviteLink] = useState("");

  // ---------- 实时转写 / 辅助 / 评价 ----------
  const [transcript, setTranscript] = useState("");
  const [assist, setAssist] = useState<AssistTip | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [error, setError] = useState("");

  // ---------- 底层连接（用 ref 保活，避免重渲染丢失）----------
  const trtcRef = useRef<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const seqRef = useRef(0);
  const taskIdRef = useRef<string | null>(null);
  const roomIdRef = useRef<number | null>(null);
  const candUidRef = useRef<string>("");
  const hrUidRef = useRef<string>("hr_hr");
  const transcriptRef = useRef("");          // 累计转写（喂实时辅助 / 兜底回写）
  const assistTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const assistSentRef = useRef("");
  const localVideoRef = useRef<HTMLVideoElement | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null);

  const setTranscriptAppend = useCallback((text: string) => {
    transcriptRef.current += text;
    setTranscript(transcriptRef.current);
  }, []);

  // 解析 URL 中的 ?candidate= 与 ?role=，支持「HR 把邀请链接发给候选人」的场景
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const c = sp.get("candidate");
    const r = sp.get("role");
    if (c) setCandidateId(c);
    if (r === "hr" || r === "candidate") setRole(r);
  }, []);

  // 候选人侧：输入 ID 后自动检查资格，决定要不要展示「资料登记」
  const checkEligibility = useCallback(async (id: string) => {
    if (!id) { setEligible(null); return; }
    const d = await videoCandidateGet(id).catch(() => null);
    if (d && d.success && d.exists) {
      setEligible(!!d.eligible);
      setEligMissing(d.missing || []);
      setProfileName(d.name || "");
      if (!d.eligible) setRegisterOpen(true);
    } else {
      // 不存在：候选人需要先登记资料生成唯一 ID
      setEligible(false);
      setEligMissing(REQUIRED_FIELDS.map((f) => f[0]));
      setRegisterOpen(true);
    }
  }, []);

  useEffect(() => {
    if (role === "candidate" && candidateId) checkEligibility(candidateId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, candidateId]);

  const onRegister = async () => {
    setRegBusy(true);
    const fields: Record<string, unknown> = {};
    for (const [key] of REQUIRED_FIELDS) fields[key] = regForm[key]?.trim() || "";
    const r = await videoRegister(fields, candidateId).catch(() => null);
    setRegBusy(false);
    if (r && r.success && r.candidate_id) {
      setCandidateId(r.candidate_id);
      setEligible(!!r.eligible);
      setEligMissing(r.missing || []);
      setProfileName(regForm["姓名"] || "");
      setRegisterOpen(false);
      setStatus(`资料已登记，候选人ID=${r.candidate_id}${r.eligible ? "，具备面试资格。" : "（资料仍需补充）"}`);
      // 同步到地址栏，方便候选人或 HR 复制
      const u = new URL(window.location.href);
      u.searchParams.set("candidate", r.candidate_id);
      window.history.replaceState({}, "", u.toString());
    } else {
      setError("登记失败：" + (r?.error || "未知错误"));
    }
  };

  // ---- 实时 ASR：用后端签好的串直接连 WebSocket，推本地麦克风 PCM（仅本端声音）----
  const connectASR = useCallback((wsUrl: string, stream: MediaStream) => {
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onopen = () => {
      const AC = window.AudioContext || (window as any).webkitAudioContext;
      const ctx: AudioContext = new AC();
      audioCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const proc = ctx.createScriptProcessor(4096, 1, 1);
      proc.onaudioprocess = (e: AudioProcessingEvent) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const samples = e.inputBuffer.getChannelData(0);
        const pcm = new Int16Array(samples.length);
        for (let i = 0; i < samples.length; i++) pcm[i] = Math.max(-1, Math.min(1, samples[i])) * 0x7fff;
        // 腾讯云实时 ASR 帧头：2字节 seq(大端) + 1字节类型(0=音频) + 1字节保留；音频负载在后
        const header = new ArrayBuffer(4);
        const dv = new DataView(header);
        dv.setUint16(0, ++seqRef.current, false); dv.setUint8(2, 0); dv.setUint8(3, 0);
        const frame = new Uint8Array(4 + pcm.byteLength);
        frame.set(new Uint8Array(header), 0); frame.set(new Uint8Array(pcm.buffer), 4);
        ws.send(frame);
      };
      src.connect(proc); proc.connect(ctx.destination);
    };
    ws.onmessage = (ev: MessageEvent) => {
      try {
        const msg = JSON.parse(ev.data as string);
        if (msg.result) {
          const line = (msg.final ? "\n" : "") + msg.result;
          setTranscriptAppend(line);
        }
      } catch { /* 忽略非 JSON */ }
    };
    ws.onerror = () => console.warn("ASR WebSocket 错误");
  }, [setTranscriptAppend]);

  // 周期性调用实时辅助（HR 专属：基于累计转写给追问/风险/STAR 建议）
  const callAssist = useCallback(async () => {
    const text = transcriptRef.current.trim();
    if (!text || text === assistSentRef.current) return;
    assistSentRef.current = text;
    try {
      const r = await videoAssist(text, familyKey);
      if (r.success && r.assist) setAssist(r.assist);
    } catch { /* 实时辅助失败不影响主流程，静默 */ }
  }, [familyKey]);

  // ---- 生成评价：优先云端录制后处理，失败则用本地转写兜底回写飞书 ----
  const runEvaluation = useCallback(async () => {
    const cid = candidateId;
    const fam = familyKey;
    try {
      if (taskIdRef.current || roomIdRef.current != null) {
        const r = await videoRecordingProcess({
          room_id: roomIdRef.current ?? undefined,
          candidate: cid,
          candidate_id: cid,
          family_key: fam,
          hr_user_id: hrUidRef.current,
          candidate_user_id: candUidRef.current,
          track_mode: "separate",
          write_feishu: true,
        });
        if (r.success) {
          setEvaluation((r.evaluation as Evaluation) || null);
          setStatus("✅ 评价已生成并回写飞书「面试记录」表（云端录制→文件识别→评分）。");
          return;
        }
        throw new Error(r.error || "process 失败");
      }
      throw new Error("无录制任务");
    } catch (e: any) {
      setStatus(`⚠ 云端录制后处理失败（${e?.message || e}），尝试用本地转写兜底回写飞书…`);
      try {
        const r2 = await videoReport({
          candidate: candidateId,
          candidate_id: candidateId,
          family_key: familyKey,
          speaker_transcript: [{ speaker: role === "hr" ? "HR" : "候选人", text: transcriptRef.current.trim() }],
        });
        if (r2.success) {
          setEvaluation((r2.evaluation as Evaluation) || null);
          setStatus("✅ 已用本地转写兜底回写飞书「面试记录」表（无云端录制源）。");
          return;
        }
        setError("回写失败：" + (r2.error || "未知"));
      } catch (e2: any) {
        setError("兜底回写异常：" + (e2?.message || e2));
      }
    }
  }, [candidateId, familyKey, role]);

  // ---- 进入房间（双方共用；role 决定用哪一路 UserSig）----
  const enterRoom = useCallback(async (room: VideoRoomResp) => {
    const TRTC = await loadTrtc();
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
    } catch (e) {
      setError("无法获取摄像头/麦克风：" + String(e));
      throw e;
    }
    streamRef.current = stream;
    if (localVideoRef.current) localVideoRef.current.srcObject = stream;

    const trtc = TRTC.create();
    trtcRef.current = trtc;
    trtc.on("track", (evt: any) => {
      if (evt.streamType === "main" && remoteVideoRef.current) remoteVideoRef.current.srcObject = evt.stream;
    });

    const me = role === "hr" ? room.interviewer! : room.candidate!;
    await trtc.enterRoom({ sdkAppId: room.sdk_app_id, userId: me.user_id, userSig: me.user_sig, roomId: room.room_id });
    await trtc.startLocalVideo({ view: localVideoRef.current! });
    await trtc.startLocalAudio();
  }, [role]);

  // ---- 开始（HR）/ 进入（候选人）----
  const start = useCallback(async () => {
    if (!candidateId.trim()) { setError("请先填写候选人ID（飞书简历库 record_id）。"); return; }
    setError("");
    setBusy(true);
    setEvaluation(null);
    transcriptRef.current = "";
    setTranscript("");
    setAssist(null);

    try {
      // 1) 后端：资格门禁 + 创建房间（拿双方 UserSig）
      setStatus("① 正在创建房间 + 签 ASR 连接串…");
      const room = await videoRoom(candidateId.trim(), "hr");
      if (!room.success) {
        setError("房间创建失败：" + (room.error || room.reason || "未知") + (room.missing?.length ? `（缺：${room.missing.join("、")}）` : ""));
        setBusy(false);
        return;
      }
      candUidRef.current = room.candidate!.user_id;
      hrUidRef.current = room.interviewer!.user_id;
      roomIdRef.current = room.room_id ?? null;
      setEligible(true);

      // 2) 签 ASR 连接串（voice_id 含角色与房间，便于后端隔离）
      const asr = await videoAsr(`${role}_${room.room_id}`);
      if (!asr.success) {
        setError("ASR 初始化失败：" + (asr.error || "未知"));
        setBusy(false);
        return;
      }

      // 3) TRTC 入房 + 摄像头麦克风
      await enterRoom(room);
      setJoined(true);

      // 4) HR：自动启动云端录制（闭环关键：结束后才有文件可识别评分）
      if (role === "hr") {
        try {
          const rec = await videoRecordingStart(room.room_id!, candidateId.trim());
          if (rec.success) {
            taskIdRef.current = rec.task_id || null;
            setStatus(`① 房间就绪。② 云端录制已启动（task_id=${taskIdRef.current}）。③ 实时转写/辅助进行中…`);
          } else {
            setStatus(`① 房间就绪。⚠ 云端录制未启动：${rec.error || ""}（结束将用本地转写兜底回写飞书）`);
          }
        } catch (e: any) {
          setStatus(`① 房间就绪。⚠ 云端录制调用异常：${e?.message || e}（结束将用本地转写兜底回写飞书）`);
        }
        // 实时辅助定时器（每 8s）
        assistTimerRef.current = setInterval(() => { callAssist(); }, 8000);
        // 生成可分享的邀请链接
        const u = new URL(window.location.href);
        u.searchParams.set("candidate", candidateId.trim());
        u.searchParams.set("role", "candidate");
        setInviteLink(u.toString());
      } else {
        setStatus("已入会，等待面试官开始面试。实时字幕进行中。");
      }

      // 5) 实时 ASR（推本地麦克风，仅本端声音；候选人侧也显示字幕）
      connectASR(asr.url!, streamRef.current!);
    } catch (e: any) {
      setError("启动失败：" + (e?.message || e));
    } finally {
      setBusy(false);
    }
  }, [candidateId, role, enterRoom, connectASR, callAssist]);

  // ---- 结束（HR 收尾；候选人仅退出）----
  const stop = useCallback(async () => {
    setBusy(true);
    setStatus("④ 正在结束：停止转写 → 退房 → 停止录制 → 生成评价…");

    // 发送结束帧并关闭 ASR
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      const header = new ArrayBuffer(4);
      const dv = new DataView(header);
      dv.setUint16(0, ++seqRef.current, false); dv.setUint8(2, 0); dv.setUint8(3, 1); // 第4字节=1 表示结束
      ws.send(new Uint8Array(header));
      ws.close();
    }
    if (assistTimerRef.current) { clearInterval(assistTimerRef.current); assistTimerRef.current = null; }
    if (trtcRef.current) { try { await trtcRef.current.exitRoom(); } catch {} trtcRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach((t) => t.stop()); streamRef.current = null; }
    if (audioCtxRef.current) { try { audioCtxRef.current.close(); } catch {} audioCtxRef.current = null; }
    if (localVideoRef.current) localVideoRef.current.srcObject = null;
    if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;

    // 候选人：只退出房间，评价由 HR 端生成
    if (role === "candidate") {
      setJoined(false);
      setStatus("你已退出面试间。面试评价将由面试官在结束后生成并回写飞书。");
      setBusy(false);
      return;
    }

    // HR：停止云端录制（让文件落 COS）
    if (taskIdRef.current) {
      try {
        await videoRecordingStop(taskIdRef.current);
        setStatus("④ 录制已停止。⑤ 正在生成评价（文件识别 + 评分 + 写飞书）…（COS 落盘可能短暂延迟）");
      } catch (e: any) {
        setStatus("④ ⚠ 停止录制异常：" + (e?.message || e) + "。仍尝试生成评价…");
      }
    }

    // ⑤ 触发后处理（识别 → 评分 → 写飞书）
    await runEvaluation();
    setJoined(false);
    setBusy(false);
  }, [role, runEvaluation]);

  // 组件卸载时清理连接
  useEffect(() => {
    return () => {
      try { wsRef.current?.close(); } catch {}
      try { trtcRef.current?.exitRoom(); } catch {}
      streamRef.current?.getTracks().forEach((t) => t.stop());
      try { audioCtxRef.current?.close(); } catch {}
      if (assistTimerRef.current) clearInterval(assistTimerRef.current);
    };
  }, []);

  // ---------- UI ----------
  const dimHtml = (evaluation?.dimensionScores || []).map((d, i) => (
    <li key={i} className="text-[13px] leading-6">
      {d.dim}：<b>{d.score ?? "-"}</b>分（{d.state || "-"}）{d.evidence ? `— ${d.evidence}` : ""}
    </li>
  ));
  const flags = evaluation?.complianceFlags || [];

  return (
    <section className="page video-interview-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">VIDEO INTERVIEW LOOP</p>
          <h1>视频面试（端到端闭环）</h1>
          <p>独立 TRTC 音视频 + 独立 ASR 实时转写 + HR 实时辅助 + 云端录制 → 文件识别 → 评分 → 回写飞书。资格门禁确保每位候选人都先填完资料再面试。</p>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-[#f3c2c2] bg-[#fdecec] px-3 py-2 text-[13px] text-[#c0392b] mb-3">
          {error}
        </div>
      )}

      {/* 角色与候选人信息条 */}
      <div className="panel mb-3" style={{ padding: 16 }}>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-[12px] text-[var(--muted)] mb-1">我的角色</label>
            <div className="inline-flex rounded-lg border border-[var(--line)] overflow-hidden">
              <button
                className={`px-4 py-2 text-[13px] ${role === "hr" ? "bg-[var(--blue)] text-white" : "bg-white text-[var(--ink)]"}`}
                onClick={() => setRole("hr")}
              >面试官（HR）</button>
              <button
                className={`px-4 py-2 text-[13px] ${role === "candidate" ? "bg-[var(--blue)] text-white" : "bg-white text-[var(--ink)]"}`}
                onClick={() => setRole("candidate")}
              >候选人</button>
            </div>
          </div>
          <div className="min-w-[220px] flex-1">
            <label className="block text-[12px] text-[var(--muted)] mb-1">
              候选人 ID（飞书简历库 record_id）
            </label>
            <input
              value={candidateId}
              onChange={(e) => setCandidateId(e.target.value.trim())}
              placeholder="如：rec_xxxxxxxx 或粘贴邀请链接自动解析"
              className="w-full rounded-lg border border-[var(--line)] px-3 py-2 text-[14px]"
            />
          </div>
          <div>
            <label className="block text-[12px] text-[var(--muted)] mb-1">岗位族</label>
            <select
              value={familyKey}
              onChange={(e) => setFamilyKey(e.target.value)}
              className="rounded-lg border border-[var(--line)] px-3 py-2 text-[14px]"
            >
              <option value="firstline">一线生产</option>
              <option value="process-equipment">工艺 / 设备</option>
              <option value="quality">质量 / 检验</option>
              <option value="procurement-logistics">采购 / 物流</option>
              <option value="production-management">现场管理</option>
            </select>
          </div>
        </div>

        {/* 候选人资格状态 + 资料登记入口 */}
        {role === "candidate" && (
          <div className="mt-3">
            {eligible === null && <span className="text-[13px] text-[var(--muted)]">输入候选人ID后自动校验面试资格…</span>}
            {eligible === true && <span className="text-[13px] text-[var(--green)]">✓ 资料完整，具备视频面试资格（{profileName || candidateId}）。</span>}
            {eligible === false && (
              <div className="mt-2 rounded-lg border border-[#f3c2c2] bg-[#fdecec] px-3 py-2 text-[13px]">
                <span className="text-[#c0392b]">✗ 尚未具备面试资格：资料未填写完整（缺 {eligMissing.join("、") || "必填项"}）。请先完成下方登记。</span>
                {!registerOpen && (
                  <button className="ml-2 underline text-[var(--blue)]" onClick={() => setRegisterOpen(true)}>去登记资料</button>
                )}
              </div>
            )}
          </div>
        )}

        {/* 资料登记表单（候选人资格门禁入口）*/}
        {registerOpen && (
          <div className="mt-3 rounded-lg border border-[var(--line)] bg-[#f8faff] p-3">
            <p className="text-[13px] font-medium mb-2">候选人资料登记（填完即生成唯一候选人ID并具备面试资格）</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {REQUIRED_FIELDS.map(([key, label, ph]) => (
                <label key={key} className="block text-[12px] text-[var(--muted)]">
                  {label}
                  <input
                    value={regForm[key] || ""}
                    onChange={(e) => setRegForm((f) => ({ ...f, [key]: e.target.value }))}
                    placeholder={ph}
                    className="mt-1 w-full rounded-lg border border-[var(--line)] px-2 py-1.5 text-[14px] text-[var(--ink)]"
                  />
                </label>
              ))}
            </div>
            <button className="mt-3 rounded-lg bg-[var(--blue)] px-4 py-2 text-[13px] text-white disabled:opacity-50"
              onClick={onRegister} disabled={regBusy}>
              {regBusy ? "提交中…" : (candidateId ? "保存并刷新资格" : "提交登记")}
            </button>
          </div>
        )}

        {/* 主操作按钮 */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {!joined ? (
            <button className="rounded-lg bg-[var(--blue)] px-5 py-2.5 text-[14px] text-white disabled:opacity-50"
              onClick={start} disabled={busy || !candidateId}>
              {busy ? "启动中…" : (role === "hr" ? "开始面试" : "进入面试间")}
            </button>
          ) : (
            <button className="rounded-lg bg-[var(--red)] px-5 py-2.5 text-[14px] text-white disabled:opacity-50"
              onClick={stop} disabled={busy}>
              {busy ? "处理中…" : (role === "hr" ? "结束并生成评价" : "退出面试间")}
            </button>
          )}

          {role === "hr" && inviteLink && (
            <div className="flex items-center gap-2">
              <input readOnly value={inviteLink} className="w-[360px] max-w-full rounded-lg border border-[var(--line)] px-2 py-2 text-[12px]" />
              <button className="rounded-lg border border-[var(--line)] px-3 py-2 text-[13px]"
                onClick={() => { navigator.clipboard?.writeText(inviteLink); setStatus("邀请链接已复制，发给候选人即可入会。"); }}>复制邀请链接</button>
            </div>
          )}
        </div>
      </div>

      {/* 视频 + 辅助 + 转写 三栏 */}
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="panel p-3">
          <h3 className="text-[14px] font-medium mb-2">本地画面（你）</h3>
          <video ref={localVideoRef} autoPlay playsInline muted className="w-full rounded-lg bg-black aspect-[4/3] object-cover" />
        </div>
        <div className="panel p-3">
          <h3 className="text-[14px] font-medium mb-2">远端画面</h3>
          <video ref={remoteVideoRef} autoPlay playsInline className="w-full rounded-lg bg-black aspect-[4/3] object-cover" />
        </div>
        <div className="panel p-3">
          <h3 className="text-[14px] font-medium mb-2">
            实时辅助（AI · DeepSeek）{role === "candidate" && <span className="text-[12px] text-[var(--muted)]">（仅面试官可见）</span>}
          </h3>
          {role === "hr" ? (
            assist ? (
              <div className="space-y-3 text-[13px] leading-6">
                <div><b className="text-[var(--blue)]">建议追问</b><br />{assist["建议追问"] || "-"}</div>
                <div><b className="text-[var(--red)]">风险预警</b><br />{assist["风险预警"] || "-"}</div>
                <div><b className="text-[var(--green)]">STAR 提示</b><br />{assist["STAR提示"] || "-"}</div>
              </div>
            ) : (
              <span className="text-[13px] text-[var(--muted)]">面试进行中，将基于实时转写给出建议追问 / 风险预警 / STAR 提示。</span>
            )
          ) : (
            <span className="text-[13px] text-[var(--muted)]">辅助面板仅对面试官开放。</span>
          )}
        </div>
      </div>

      {/* 实时转写 */}
      <div className="panel mt-3 p-3">
        <h3 className="text-[14px] font-medium mb-2">实时转写（独立 ASR）</h3>
        <div className="h-[150px] overflow-y-auto whitespace-pre-wrap rounded-lg border border-[var(--line)] bg-[#fafbfc] p-3 text-[13px] leading-6">
          {transcript || "点击「开始面试 / 进入面试间」后，麦克风音频会实时推到腾讯云 ASR，转写显示在此。"}
        </div>
      </div>

      {/* 面试评价（闭环产出）*/}
      {evaluation && (
        <div className="panel mt-3 p-4">
          <h3 className="text-[14px] font-medium mb-2">面试评价（自动识别 → 评分 → 回写飞书）</h3>
          <div className="flex flex-wrap items-center gap-4">
            <span className="inline-block rounded-full bg-[#e8f1fb] px-3 py-1 text-[13px] text-[var(--blue)]">综合评级 <b>{evaluation.overallRating ?? "-"}</b> / 10</span>
            <span className="text-[13px]"><b>录用建议（AI 辅助，不替决策）</b>：{evaluation.hiringSuggestion || "-"}</span>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <div>
              <b className="text-[13px]">维度分</b>
              <ul className="mt-1 list-disc pl-5">{dimHtml.length ? dimHtml : <li className="text-[13px]">-</li>}</ul>
            </div>
            <div className="text-[13px]">
              <b>合规预警</b>：{flags.length ? flags.join("；") : "无"}
              <div className="mt-2"><b>面试纪要</b>：{evaluation.transcriptSummary || "-"}</div>
            </div>
          </div>
        </div>
      )}

      {/* 流程状态 */}
      <div className="panel mt-3 p-3">
        <h3 className="text-[14px] font-medium mb-2">流程状态</h3>
        <div className="whitespace-pre-wrap text-[13px] leading-6 text-[var(--muted)]">{status}</div>
      </div>
    </section>
  );
}
