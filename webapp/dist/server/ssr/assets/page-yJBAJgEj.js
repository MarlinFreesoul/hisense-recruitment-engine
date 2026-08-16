import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Fragment as Fragment$1, jsx, jsxs } from "react/jsx-runtime";
//#region lib/api.ts
var API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
async function fetchJobs() {
	return (await (await fetch(`${API_BASE}/jobs`)).json()).jobs || [];
}
async function fetchResults() {
	return (await (await fetch(`${API_BASE}/results`)).json()).results || [];
}
async function fetchInterviewQuestions(candidate, assessment = "") {
	const url = `${API_BASE}/interview/questions?candidate=${encodeURIComponent(candidate)}` + (assessment ? `&assessment=${encodeURIComponent(assessment)}` : "");
	return (await fetch(url)).json();
}
async function submitInterview(candidate, job, answers) {
	return (await fetch(`${API_BASE}/interview/submit`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			candidate,
			job,
			answers
		})
	})).json();
}
async function fetchTalentPool(jobFamily = "") {
	const url = `${API_BASE}/talent-pool${jobFamily ? `?job_family=${encodeURIComponent(jobFamily)}` : ""}`;
	return (await (await fetch(url)).json()).comparison || [];
}
async function seedDemo() {
	return (await fetch(`${API_BASE}/demo/seed`, { method: "POST" })).json();
}
async function offerFallback(jobFamily, rejectedId) {
	return (await fetch(`${API_BASE}/decision/offer-fallback`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			job_family: jobFamily,
			rejected_id: rejectedId
		})
	})).json();
}
async function generateJd(jobFamily, params = {}) {
	return (await fetch(`${API_BASE}/jd/generate`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			job_family: jobFamily,
			params
		})
	})).json();
}
async function saveJd(jobFamily, params = {}) {
	return (await fetch(`${API_BASE}/jd/save`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			job_family: jobFamily,
			params
		})
	})).json();
}
async function screenResume(text, jobName, jobFamily) {
	return (await fetch(`${API_BASE}/screen`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			text,
			job_name: jobName,
			job_family: jobFamily,
			write_feishu: false
		})
	})).json();
}
async function uploadResume(file, jobName, jobFamily) {
	const fd = new FormData();
	fd.append("file", file);
	fd.append("job_name", jobName);
	fd.append("job_family", jobFamily);
	fd.append("write_feishu", "false");
	return (await fetch(`${API_BASE}/screen/upload`, {
		method: "POST",
		body: fd
	})).json();
}
async function departmentPush(payload) {
	return (await fetch(`${API_BASE}/review/department-push`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(payload)
	})).json();
}
async function submitDepartmentDecision(payload) {
	return (await fetch(`${API_BASE}/review/department-decision`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(payload)
	})).json();
}
async function fetchDecisions() {
	return (await (await fetch(`${API_BASE}/review/decisions`)).json()).decisions || [];
}
async function videoRegister(fields, recordId = "") {
	return (await fetch(`${API_BASE}/video/candidate/register`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			record_id: recordId,
			fields
		})
	})).json();
}
async function videoCandidateGet(candidateId) {
	return (await fetch(`${API_BASE}/video/candidate/${encodeURIComponent(candidateId)}`)).json();
}
async function videoRoom(candidate, interviewer = "hr", roomId) {
	return (await fetch(`${API_BASE}/video/room`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			candidate,
			interviewer,
			room_id: roomId ?? null
		})
	})).json();
}
async function videoAsr(voiceId) {
	return (await fetch(`${API_BASE}/video/asr?voice_id=${encodeURIComponent(voiceId)}`)).json();
}
async function videoAssist(transcript, familyKey = "firstline") {
	return (await fetch(`${API_BASE}/video/assist`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			transcript,
			family_key: familyKey
		})
	})).json();
}
async function videoRecordingStart(roomId, candidate) {
	return (await fetch(`${API_BASE}/video/recording/start`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			room_id: roomId,
			candidate
		})
	})).json();
}
async function videoRecordingStop(taskId) {
	return (await fetch(`${API_BASE}/video/recording/stop`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ task_id: taskId })
	})).json();
}
async function videoRecordingProcess(payload) {
	return (await fetch(`${API_BASE}/video/recording/process`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			family_key: "firstline",
			track_mode: "separate",
			write_feishu: true,
			...payload
		})
	})).json();
}
async function videoReport(payload) {
	return (await fetch(`${API_BASE}/video/report`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			family_key: "firstline",
			...payload
		})
	})).json();
}
//#endregion
//#region components/VideoInterview.tsx
var REQUIRED_FIELDS = [
	[
		"姓名",
		"姓名",
		"如：张三"
	],
	[
		"最近职位",
		"最近职位",
		"如：设备维修工程师"
	],
	[
		"最近公司",
		"最近公司",
		"如：某制造企业"
	],
	[
		"工作年限",
		"工作年限",
		"如：5"
	]
];
var trtcPromise = null;
function loadTrtc() {
	if (typeof window === "undefined") return Promise.reject(/* @__PURE__ */ new Error("非浏览器环境"));
	const w = window;
	if (w.TRTC) return Promise.resolve(w.TRTC);
	if (trtcPromise) return trtcPromise;
	trtcPromise = new Promise((resolve, reject) => {
		const s = document.createElement("script");
		s.src = "https://web.sdk.qcloud.com/trtc/webrtc/v5/trtc.js";
		s.async = true;
		s.onload = () => w.TRTC ? resolve(w.TRTC) : reject(/* @__PURE__ */ new Error("TRTC 全局对象缺失"));
		s.onerror = () => reject(/* @__PURE__ */ new Error("TRTC SDK 加载失败，请检查网络后重试"));
		document.head.appendChild(s);
	});
	return trtcPromise;
}
function VideoInterview() {
	const [role, setRole] = useState("hr");
	const [candidateId, setCandidateId] = useState("");
	const [familyKey, setFamilyKey] = useState("firstline");
	const [profileName, setProfileName] = useState("");
	const [eligible, setEligible] = useState(null);
	const [eligMissing, setEligMissing] = useState([]);
	const [registerOpen, setRegisterOpen] = useState(false);
	const [regForm, setRegForm] = useState({
		姓名: "",
		最近职位: "",
		最近公司: "",
		工作年限: ""
	});
	const [regBusy, setRegBusy] = useState(false);
	const [joined, setJoined] = useState(false);
	const [busy, setBusy] = useState(false);
	const [status, setStatus] = useState("就绪。HR 点击「开始面试」、候选人点击「进入面试间」启动闭环。");
	const [inviteLink, setInviteLink] = useState("");
	const [transcript, setTranscript] = useState("");
	const [assist, setAssist] = useState(null);
	const [evaluation, setEvaluation] = useState(null);
	const [error, setError] = useState("");
	const trtcRef = useRef(null);
	const wsRef = useRef(null);
	const streamRef = useRef(null);
	const audioCtxRef = useRef(null);
	const seqRef = useRef(0);
	const taskIdRef = useRef(null);
	const roomIdRef = useRef(null);
	const candUidRef = useRef("");
	const hrUidRef = useRef("hr_hr");
	const transcriptRef = useRef("");
	const assistTimerRef = useRef(null);
	const assistSentRef = useRef("");
	const localVideoRef = useRef(null);
	const remoteVideoRef = useRef(null);
	const setTranscriptAppend = useCallback((text) => {
		transcriptRef.current += text;
		setTranscript(transcriptRef.current);
	}, []);
	useEffect(() => {
		const sp = new URLSearchParams(window.location.search);
		const c = sp.get("candidate");
		const r = sp.get("role");
		if (c) setCandidateId(c);
		if (r === "hr" || r === "candidate") setRole(r);
	}, []);
	const checkEligibility = useCallback(async (id) => {
		if (!id) {
			setEligible(null);
			return;
		}
		const d = await videoCandidateGet(id).catch(() => null);
		if (d && d.success && d.exists) {
			setEligible(!!d.eligible);
			setEligMissing(d.missing || []);
			setProfileName(d.name || "");
			if (!d.eligible) setRegisterOpen(true);
		} else {
			setEligible(false);
			setEligMissing(REQUIRED_FIELDS.map((f) => f[0]));
			setRegisterOpen(true);
		}
	}, []);
	useEffect(() => {
		if (role === "candidate" && candidateId) checkEligibility(candidateId);
	}, [role, candidateId]);
	const onRegister = async () => {
		setRegBusy(true);
		const fields = {};
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
			const u = new URL(window.location.href);
			u.searchParams.set("candidate", r.candidate_id);
			window.history.replaceState({}, "", u.toString());
		} else setError("登记失败：" + (r?.error || "未知错误"));
	};
	const connectASR = useCallback((wsUrl, stream) => {
		const ws = new WebSocket(wsUrl);
		wsRef.current = ws;
		ws.onopen = () => {
			const ctx = new (window.AudioContext || window.webkitAudioContext)();
			audioCtxRef.current = ctx;
			const src = ctx.createMediaStreamSource(stream);
			const proc = ctx.createScriptProcessor(4096, 1, 1);
			proc.onaudioprocess = (e) => {
				if (ws.readyState !== WebSocket.OPEN) return;
				const samples = e.inputBuffer.getChannelData(0);
				const pcm = new Int16Array(samples.length);
				for (let i = 0; i < samples.length; i++) pcm[i] = Math.max(-1, Math.min(1, samples[i])) * 32767;
				const header = /* @__PURE__ */ new ArrayBuffer(4);
				const dv = new DataView(header);
				dv.setUint16(0, ++seqRef.current, false);
				dv.setUint8(2, 0);
				dv.setUint8(3, 0);
				const frame = new Uint8Array(4 + pcm.byteLength);
				frame.set(new Uint8Array(header), 0);
				frame.set(new Uint8Array(pcm.buffer), 4);
				ws.send(frame);
			};
			src.connect(proc);
			proc.connect(ctx.destination);
		};
		ws.onmessage = (ev) => {
			try {
				const msg = JSON.parse(ev.data);
				if (msg.result) setTranscriptAppend((msg.final ? "\n" : "") + msg.result);
			} catch {}
		};
		ws.onerror = () => console.warn("ASR WebSocket 错误");
	}, [setTranscriptAppend]);
	const callAssist = useCallback(async () => {
		const text = transcriptRef.current.trim();
		if (!text || text === assistSentRef.current) return;
		assistSentRef.current = text;
		try {
			const r = await videoAssist(text, familyKey);
			if (r.success && r.assist) setAssist(r.assist);
		} catch {}
	}, [familyKey]);
	const runEvaluation = useCallback(async () => {
		const cid = candidateId;
		const fam = familyKey;
		try {
			if (taskIdRef.current || roomIdRef.current != null) {
				const r = await videoRecordingProcess({
					room_id: roomIdRef.current ?? void 0,
					candidate: cid,
					candidate_id: cid,
					family_key: fam,
					hr_user_id: hrUidRef.current,
					candidate_user_id: candUidRef.current,
					track_mode: "separate",
					write_feishu: true
				});
				if (r.success) {
					setEvaluation(r.evaluation || null);
					setStatus("✅ 评价已生成并回写飞书「面试记录」表（云端录制→文件识别→评分）。");
					return;
				}
				throw new Error(r.error || "process 失败");
			}
			throw new Error("无录制任务");
		} catch (e) {
			setStatus(`⚠ 云端录制后处理失败（${e?.message || e}），尝试用本地转写兜底回写飞书…`);
			try {
				const r2 = await videoReport({
					candidate: candidateId,
					candidate_id: candidateId,
					family_key: familyKey,
					speaker_transcript: [{
						speaker: role === "hr" ? "HR" : "候选人",
						text: transcriptRef.current.trim()
					}]
				});
				if (r2.success) {
					setEvaluation(r2.evaluation || null);
					setStatus("✅ 已用本地转写兜底回写飞书「面试记录」表（无云端录制源）。");
					return;
				}
				setError("回写失败：" + (r2.error || "未知"));
			} catch (e2) {
				setError("兜底回写异常：" + (e2?.message || e2));
			}
		}
	}, [
		candidateId,
		familyKey,
		role
	]);
	const enterRoom = useCallback(async (room) => {
		const TRTC = await loadTrtc();
		let stream;
		try {
			stream = await navigator.mediaDevices.getUserMedia({
				audio: true,
				video: true
			});
		} catch (e) {
			setError("无法获取摄像头/麦克风：" + String(e));
			throw e;
		}
		streamRef.current = stream;
		if (localVideoRef.current) localVideoRef.current.srcObject = stream;
		const trtc = TRTC.create();
		trtcRef.current = trtc;
		trtc.on("track", (evt) => {
			if (evt.streamType === "main" && remoteVideoRef.current) remoteVideoRef.current.srcObject = evt.stream;
		});
		const me = role === "hr" ? room.interviewer : room.candidate;
		await trtc.enterRoom({
			sdkAppId: room.sdk_app_id,
			userId: me.user_id,
			userSig: me.user_sig,
			roomId: room.room_id
		});
		await trtc.startLocalVideo({ view: localVideoRef.current });
		await trtc.startLocalAudio();
	}, [role]);
	const start = useCallback(async () => {
		if (!candidateId.trim()) {
			setError("请先填写候选人ID（飞书简历库 record_id）。");
			return;
		}
		setError("");
		setBusy(true);
		setEvaluation(null);
		transcriptRef.current = "";
		setTranscript("");
		setAssist(null);
		try {
			setStatus("① 正在创建房间 + 签 ASR 连接串…");
			const room = await videoRoom(candidateId.trim(), "hr");
			if (!room.success) {
				setError("房间创建失败：" + (room.error || room.reason || "未知") + (room.missing?.length ? `（缺：${room.missing.join("、")}）` : ""));
				setBusy(false);
				return;
			}
			candUidRef.current = room.candidate.user_id;
			hrUidRef.current = room.interviewer.user_id;
			roomIdRef.current = room.room_id ?? null;
			setEligible(true);
			const asr = await videoAsr(`${role}_${room.room_id}`);
			if (!asr.success) {
				setError("ASR 初始化失败：" + (asr.error || "未知"));
				setBusy(false);
				return;
			}
			await enterRoom(room);
			setJoined(true);
			if (role === "hr") {
				try {
					const rec = await videoRecordingStart(room.room_id, candidateId.trim());
					if (rec.success) {
						taskIdRef.current = rec.task_id || null;
						setStatus(`① 房间就绪。② 云端录制已启动（task_id=${taskIdRef.current}）。③ 实时转写/辅助进行中…`);
					} else setStatus(`① 房间就绪。⚠ 云端录制未启动：${rec.error || ""}（结束将用本地转写兜底回写飞书）`);
				} catch (e) {
					setStatus(`① 房间就绪。⚠ 云端录制调用异常：${e?.message || e}（结束将用本地转写兜底回写飞书）`);
				}
				assistTimerRef.current = setInterval(() => {
					callAssist();
				}, 8e3);
				const u = new URL(window.location.href);
				u.searchParams.set("candidate", candidateId.trim());
				u.searchParams.set("role", "candidate");
				setInviteLink(u.toString());
			} else setStatus("已入会，等待面试官开始面试。实时字幕进行中。");
			connectASR(asr.url, streamRef.current);
		} catch (e) {
			setError("启动失败：" + (e?.message || e));
		} finally {
			setBusy(false);
		}
	}, [
		candidateId,
		role,
		enterRoom,
		connectASR,
		callAssist
	]);
	const stop = useCallback(async () => {
		setBusy(true);
		setStatus("④ 正在结束：停止转写 → 退房 → 停止录制 → 生成评价…");
		const ws = wsRef.current;
		if (ws && ws.readyState === WebSocket.OPEN) {
			const header = /* @__PURE__ */ new ArrayBuffer(4);
			const dv = new DataView(header);
			dv.setUint16(0, ++seqRef.current, false);
			dv.setUint8(2, 0);
			dv.setUint8(3, 1);
			ws.send(new Uint8Array(header));
			ws.close();
		}
		if (assistTimerRef.current) {
			clearInterval(assistTimerRef.current);
			assistTimerRef.current = null;
		}
		if (trtcRef.current) {
			try {
				await trtcRef.current.exitRoom();
			} catch {}
			trtcRef.current = null;
		}
		if (streamRef.current) {
			streamRef.current.getTracks().forEach((t) => t.stop());
			streamRef.current = null;
		}
		if (audioCtxRef.current) {
			try {
				audioCtxRef.current.close();
			} catch {}
			audioCtxRef.current = null;
		}
		if (localVideoRef.current) localVideoRef.current.srcObject = null;
		if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
		if (role === "candidate") {
			setJoined(false);
			setStatus("你已退出面试间。面试评价将由面试官在结束后生成并回写飞书。");
			setBusy(false);
			return;
		}
		if (taskIdRef.current) try {
			await videoRecordingStop(taskIdRef.current);
			setStatus("④ 录制已停止。⑤ 正在生成评价（文件识别 + 评分 + 写飞书）…（COS 落盘可能短暂延迟）");
		} catch (e) {
			setStatus("④ ⚠ 停止录制异常：" + (e?.message || e) + "。仍尝试生成评价…");
		}
		await runEvaluation();
		setJoined(false);
		setBusy(false);
	}, [role, runEvaluation]);
	useEffect(() => {
		return () => {
			try {
				wsRef.current?.close();
			} catch {}
			try {
				trtcRef.current?.exitRoom();
			} catch {}
			streamRef.current?.getTracks().forEach((t) => t.stop());
			try {
				audioCtxRef.current?.close();
			} catch {}
			if (assistTimerRef.current) clearInterval(assistTimerRef.current);
		};
	}, []);
	const dimHtml = (evaluation?.dimensionScores || []).map((d, i) => /* @__PURE__ */ jsxs("li", {
		className: "text-[13px] leading-6",
		children: [
			d.dim,
			"：",
			/* @__PURE__ */ jsx("b", { children: d.score ?? "-" }),
			"分（",
			d.state || "-",
			"）",
			d.evidence ? `— ${d.evidence}` : ""
		]
	}, i));
	const flags = evaluation?.complianceFlags || [];
	return /* @__PURE__ */ jsxs("section", {
		className: "page video-interview-page",
		children: [
			/* @__PURE__ */ jsx("div", {
				className: "page-heading",
				children: /* @__PURE__ */ jsxs("div", { children: [
					/* @__PURE__ */ jsx("p", {
						className: "eyebrow",
						children: "VIDEO INTERVIEW LOOP"
					}),
					/* @__PURE__ */ jsx("h1", { children: "视频面试（端到端闭环）" }),
					/* @__PURE__ */ jsx("p", { children: "独立 TRTC 音视频 + 独立 ASR 实时转写 + HR 实时辅助 + 云端录制 → 文件识别 → 评分 → 回写飞书。资格门禁确保每位候选人都先填完资料再面试。" })
				] })
			}),
			error && /* @__PURE__ */ jsx("div", {
				className: "rounded-lg border border-[#f3c2c2] bg-[#fdecec] px-3 py-2 text-[13px] text-[#c0392b] mb-3",
				children: error
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "panel mb-3",
				style: { padding: 16 },
				children: [
					/* @__PURE__ */ jsxs("div", {
						className: "flex flex-wrap items-end gap-3",
						children: [
							/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
								className: "block text-[12px] text-[var(--muted)] mb-1",
								children: "我的角色"
							}), /* @__PURE__ */ jsxs("div", {
								className: "inline-flex rounded-lg border border-[var(--line)] overflow-hidden",
								children: [/* @__PURE__ */ jsx("button", {
									className: `px-4 py-2 text-[13px] ${role === "hr" ? "bg-[var(--blue)] text-white" : "bg-white text-[var(--ink)]"}`,
									onClick: () => setRole("hr"),
									children: "面试官（HR）"
								}), /* @__PURE__ */ jsx("button", {
									className: `px-4 py-2 text-[13px] ${role === "candidate" ? "bg-[var(--blue)] text-white" : "bg-white text-[var(--ink)]"}`,
									onClick: () => setRole("candidate"),
									children: "候选人"
								})]
							})] }),
							/* @__PURE__ */ jsxs("div", {
								className: "min-w-[220px] flex-1",
								children: [/* @__PURE__ */ jsx("label", {
									className: "block text-[12px] text-[var(--muted)] mb-1",
									children: "候选人 ID（飞书简历库 record_id）"
								}), /* @__PURE__ */ jsx("input", {
									value: candidateId,
									onChange: (e) => setCandidateId(e.target.value.trim()),
									placeholder: "如：rec_xxxxxxxx 或粘贴邀请链接自动解析",
									className: "w-full rounded-lg border border-[var(--line)] px-3 py-2 text-[14px]"
								})]
							}),
							/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("label", {
								className: "block text-[12px] text-[var(--muted)] mb-1",
								children: "岗位族"
							}), /* @__PURE__ */ jsxs("select", {
								value: familyKey,
								onChange: (e) => setFamilyKey(e.target.value),
								className: "rounded-lg border border-[var(--line)] px-3 py-2 text-[14px]",
								children: [
									/* @__PURE__ */ jsx("option", {
										value: "firstline",
										children: "一线生产"
									}),
									/* @__PURE__ */ jsx("option", {
										value: "process-equipment",
										children: "工艺 / 设备"
									}),
									/* @__PURE__ */ jsx("option", {
										value: "quality",
										children: "质量 / 检验"
									}),
									/* @__PURE__ */ jsx("option", {
										value: "procurement-logistics",
										children: "采购 / 物流"
									}),
									/* @__PURE__ */ jsx("option", {
										value: "production-management",
										children: "现场管理"
									})
								]
							})] })
						]
					}),
					role === "candidate" && /* @__PURE__ */ jsxs("div", {
						className: "mt-3",
						children: [
							eligible === null && /* @__PURE__ */ jsx("span", {
								className: "text-[13px] text-[var(--muted)]",
								children: "输入候选人ID后自动校验面试资格…"
							}),
							eligible === true && /* @__PURE__ */ jsxs("span", {
								className: "text-[13px] text-[var(--green)]",
								children: [
									"✓ 资料完整，具备视频面试资格（",
									profileName || candidateId,
									"）。"
								]
							}),
							eligible === false && /* @__PURE__ */ jsxs("div", {
								className: "mt-2 rounded-lg border border-[#f3c2c2] bg-[#fdecec] px-3 py-2 text-[13px]",
								children: [/* @__PURE__ */ jsxs("span", {
									className: "text-[#c0392b]",
									children: [
										"✗ 尚未具备面试资格：资料未填写完整（缺 ",
										eligMissing.join("、") || "必填项",
										"）。请先完成下方登记。"
									]
								}), !registerOpen && /* @__PURE__ */ jsx("button", {
									className: "ml-2 underline text-[var(--blue)]",
									onClick: () => setRegisterOpen(true),
									children: "去登记资料"
								})]
							})
						]
					}),
					registerOpen && /* @__PURE__ */ jsxs("div", {
						className: "mt-3 rounded-lg border border-[var(--line)] bg-[#f8faff] p-3",
						children: [
							/* @__PURE__ */ jsx("p", {
								className: "text-[13px] font-medium mb-2",
								children: "候选人资料登记（填完即生成唯一候选人ID并具备面试资格）"
							}),
							/* @__PURE__ */ jsx("div", {
								className: "grid grid-cols-2 gap-2 sm:grid-cols-4",
								children: REQUIRED_FIELDS.map(([key, label, ph]) => /* @__PURE__ */ jsxs("label", {
									className: "block text-[12px] text-[var(--muted)]",
									children: [label, /* @__PURE__ */ jsx("input", {
										value: regForm[key] || "",
										onChange: (e) => setRegForm((f) => ({
											...f,
											[key]: e.target.value
										})),
										placeholder: ph,
										className: "mt-1 w-full rounded-lg border border-[var(--line)] px-2 py-1.5 text-[14px] text-[var(--ink)]"
									})]
								}, key))
							}),
							/* @__PURE__ */ jsx("button", {
								className: "mt-3 rounded-lg bg-[var(--blue)] px-4 py-2 text-[13px] text-white disabled:opacity-50",
								onClick: onRegister,
								disabled: regBusy,
								children: regBusy ? "提交中…" : candidateId ? "保存并刷新资格" : "提交登记"
							})
						]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "mt-3 flex flex-wrap items-center gap-2",
						children: [!joined ? /* @__PURE__ */ jsx("button", {
							className: "rounded-lg bg-[var(--blue)] px-5 py-2.5 text-[14px] text-white disabled:opacity-50",
							onClick: start,
							disabled: busy || !candidateId,
							children: busy ? "启动中…" : role === "hr" ? "开始面试" : "进入面试间"
						}) : /* @__PURE__ */ jsx("button", {
							className: "rounded-lg bg-[var(--red)] px-5 py-2.5 text-[14px] text-white disabled:opacity-50",
							onClick: stop,
							disabled: busy,
							children: busy ? "处理中…" : role === "hr" ? "结束并生成评价" : "退出面试间"
						}), role === "hr" && inviteLink && /* @__PURE__ */ jsxs("div", {
							className: "flex items-center gap-2",
							children: [/* @__PURE__ */ jsx("input", {
								readOnly: true,
								value: inviteLink,
								className: "w-[360px] max-w-full rounded-lg border border-[var(--line)] px-2 py-2 text-[12px]"
							}), /* @__PURE__ */ jsx("button", {
								className: "rounded-lg border border-[var(--line)] px-3 py-2 text-[13px]",
								onClick: () => {
									navigator.clipboard?.writeText(inviteLink);
									setStatus("邀请链接已复制，发给候选人即可入会。");
								},
								children: "复制邀请链接"
							})]
						})]
					})
				]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "grid gap-3 lg:grid-cols-3",
				children: [
					/* @__PURE__ */ jsxs("div", {
						className: "panel p-3",
						children: [/* @__PURE__ */ jsx("h3", {
							className: "text-[14px] font-medium mb-2",
							children: "本地画面（你）"
						}), /* @__PURE__ */ jsx("video", {
							ref: localVideoRef,
							autoPlay: true,
							playsInline: true,
							muted: true,
							className: "w-full rounded-lg bg-black aspect-[4/3] object-cover"
						})]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "panel p-3",
						children: [/* @__PURE__ */ jsx("h3", {
							className: "text-[14px] font-medium mb-2",
							children: "远端画面"
						}), /* @__PURE__ */ jsx("video", {
							ref: remoteVideoRef,
							autoPlay: true,
							playsInline: true,
							className: "w-full rounded-lg bg-black aspect-[4/3] object-cover"
						})]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "panel p-3",
						children: [/* @__PURE__ */ jsxs("h3", {
							className: "text-[14px] font-medium mb-2",
							children: ["实时辅助（AI · DeepSeek）", role === "candidate" && /* @__PURE__ */ jsx("span", {
								className: "text-[12px] text-[var(--muted)]",
								children: "（仅面试官可见）"
							})]
						}), role === "hr" ? assist ? /* @__PURE__ */ jsxs("div", {
							className: "space-y-3 text-[13px] leading-6",
							children: [
								/* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("b", {
										className: "text-[var(--blue)]",
										children: "建议追问"
									}),
									/* @__PURE__ */ jsx("br", {}),
									assist["建议追问"] || "-"
								] }),
								/* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("b", {
										className: "text-[var(--red)]",
										children: "风险预警"
									}),
									/* @__PURE__ */ jsx("br", {}),
									assist["风险预警"] || "-"
								] }),
								/* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("b", {
										className: "text-[var(--green)]",
										children: "STAR 提示"
									}),
									/* @__PURE__ */ jsx("br", {}),
									assist["STAR提示"] || "-"
								] })
							]
						}) : /* @__PURE__ */ jsx("span", {
							className: "text-[13px] text-[var(--muted)]",
							children: "面试进行中，将基于实时转写给出建议追问 / 风险预警 / STAR 提示。"
						}) : /* @__PURE__ */ jsx("span", {
							className: "text-[13px] text-[var(--muted)]",
							children: "辅助面板仅对面试官开放。"
						})]
					})
				]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "panel mt-3 p-3",
				children: [/* @__PURE__ */ jsx("h3", {
					className: "text-[14px] font-medium mb-2",
					children: "实时转写（独立 ASR）"
				}), /* @__PURE__ */ jsx("div", {
					className: "h-[150px] overflow-y-auto whitespace-pre-wrap rounded-lg border border-[var(--line)] bg-[#fafbfc] p-3 text-[13px] leading-6",
					children: transcript || "点击「开始面试 / 进入面试间」后，麦克风音频会实时推到腾讯云 ASR，转写显示在此。"
				})]
			}),
			evaluation && /* @__PURE__ */ jsxs("div", {
				className: "panel mt-3 p-4",
				children: [
					/* @__PURE__ */ jsx("h3", {
						className: "text-[14px] font-medium mb-2",
						children: "面试评价（自动识别 → 评分 → 回写飞书）"
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "flex flex-wrap items-center gap-4",
						children: [/* @__PURE__ */ jsxs("span", {
							className: "inline-block rounded-full bg-[#e8f1fb] px-3 py-1 text-[13px] text-[var(--blue)]",
							children: [
								"综合评级 ",
								/* @__PURE__ */ jsx("b", { children: evaluation.overallRating ?? "-" }),
								" / 10"
							]
						}), /* @__PURE__ */ jsxs("span", {
							className: "text-[13px]",
							children: [
								/* @__PURE__ */ jsx("b", { children: "录用建议（AI 辅助，不替决策）" }),
								"：",
								evaluation.hiringSuggestion || "-"
							]
						})]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "mt-3 grid gap-3 md:grid-cols-2",
						children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", {
							className: "text-[13px]",
							children: "维度分"
						}), /* @__PURE__ */ jsx("ul", {
							className: "mt-1 list-disc pl-5",
							children: dimHtml.length ? dimHtml : /* @__PURE__ */ jsx("li", {
								className: "text-[13px]",
								children: "-"
							})
						})] }), /* @__PURE__ */ jsxs("div", {
							className: "text-[13px]",
							children: [
								/* @__PURE__ */ jsx("b", { children: "合规预警" }),
								"：",
								flags.length ? flags.join("；") : "无",
								/* @__PURE__ */ jsxs("div", {
									className: "mt-2",
									children: [
										/* @__PURE__ */ jsx("b", { children: "面试纪要" }),
										"：",
										evaluation.transcriptSummary || "-"
									]
								})
							]
						})]
					})
				]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "panel mt-3 p-3",
				children: [/* @__PURE__ */ jsx("h3", {
					className: "text-[14px] font-medium mb-2",
					children: "流程状态"
				}), /* @__PURE__ */ jsx("div", {
					className: "whitespace-pre-wrap text-[13px] leading-6 text-[var(--muted)]",
					children: status
				})]
			})
		]
	});
}
//#endregion
//#region app/page.tsx
var emptyJob = {
	id: 0,
	title: "加载中…",
	type: "",
	salary: "",
	location: "",
	experience: "",
	education: "",
	status: "待审核",
	risk: "低"
};
var emptyCandidate = {
	id: 0,
	name: "加载中…",
	initials: "?",
	role: "",
	score: 0,
	stage: "AI初筛",
	phone: "",
	skills: [],
	evidence: [],
	gap: ""
};
function mapJob(apiJob, index) {
	return {
		id: index + 1,
		title: apiJob.岗位名称 || "未命名岗位",
		type: apiJob.招聘类型 || "待分类",
		salary: "面议",
		location: apiJob.城市 || "佛山",
		experience: "不限",
		education: "不限",
		status: apiJob.当前状态 === "招聘中" ? "已发布" : "待审核",
		risk: "中"
	};
}
function mapCandidate(apiResult, index) {
	const name = apiResult.候选人 || "未知";
	return {
		id: index + 1,
		name,
		initials: name.slice(0, 1),
		role: apiResult.岗位名称 || "",
		score: apiResult.匹配度 ?? 0,
		stage: apiResult.推荐结论 === "通过筛选" ? "待面试" : "AI初筛",
		phone: "",
		skills: [],
		evidence: apiResult.匹配总结 ? [apiResult.匹配总结] : [],
		gap: apiResult.风险等级 ? `风险等级：${apiResult.风险等级}` : ""
	};
}
var navItems = [
	[
		"dashboard",
		"运营驾驶舱",
		"⌁"
	],
	[
		"jobs",
		"岗位治理",
		"▦"
	],
	[
		"candidates",
		"人才匹配",
		"◎"
	],
	[
		"screening",
		"上传即打分",
		"◇"
	],
	[
		"evaluation",
		"人才评价汇总",
		"▤"
	],
	[
		"interview",
		"视频面试",
		"▶"
	]
];
function Home() {
	const [active, setActive] = useState("dashboard");
	const [jobs, setJobs] = useState([]);
	const [allJobCount, setAllJobCount] = useState(0);
	const [candidates, setCandidates] = useState([]);
	const [selectedJob, setSelectedJob] = useState(emptyJob);
	const [selectedCandidate, setSelectedCandidate] = useState(emptyCandidate);
	const [query, setQuery] = useState("");
	const [toast, setToast] = useState("");
	const [screenStep, setScreenStep] = useState(1);
	const [loading, setLoading] = useState(true);
	const [uploading, setUploading] = useState(false);
	useEffect(() => {
		fetchJobs().then((apiJobs) => {
			const mapped = apiJobs.map(mapJob);
			if (mapped.length) {
				setJobs(mapped);
				setAllJobCount(mapped.length);
				setSelectedJob(mapped[0]);
			}
		}).catch(() => void 0).finally(() => setLoading(false));
		fetchResults().then((apiResults) => {
			const mapped = apiResults.map(mapCandidate);
			if (mapped.length) {
				setCandidates(mapped);
				setSelectedCandidate(mapped[0]);
			}
		}).catch(() => void 0);
	}, []);
	const notify = (message) => {
		setToast(message);
		window.setTimeout(() => setToast(""), 2400);
	};
	const filteredJobs = useMemo(() => jobs.filter((job) => `${job.title}${job.type}`.toLowerCase().includes(query.toLowerCase())), [jobs, query]);
	const duplicateRate = 0;
	const approveJob = () => {
		setJobs((current) => current.map((job) => job.id === selectedJob.id ? {
			...job,
			status: "已发布",
			risk: "低"
		} : job));
		setSelectedJob({
			...selectedJob,
			status: "已发布",
			risk: "低"
		});
		notify("岗位已通过人工复核，并发布到模拟渠道");
	};
	const scheduleInterview = () => {
		setCandidates((current) => current.map((item) => item.id === selectedCandidate.id ? {
			...item,
			stage: "待面试"
		} : item));
		setSelectedCandidate({
			...selectedCandidate,
			stage: "待面试"
		});
		notify("面试已安排：明日 14:30 · 容桂园区");
	};
	const onUploadCandidate = async (e) => {
		const f = e.target.files?.[0];
		if (!f) return;
		setUploading(true);
		const r = await uploadResume(f, "", "firstline").catch(() => null);
		setUploading(false);
		if (r && r.success) {
			notify(`已解析并打分：${r.result?.匹配度}分 / ${r.result?.等级}，已入人才池`);
			setActive("evaluation");
		} else notify("解析失败：" + (r?.error || "未知"));
		e.target.value = "";
	};
	return /* @__PURE__ */ jsxs("main", {
		className: "app-shell",
		children: [
			/* @__PURE__ */ jsxs("aside", {
				className: "sidebar",
				children: [
					/* @__PURE__ */ jsxs("div", {
						className: "brand",
						children: [/* @__PURE__ */ jsx("span", {
							className: "brand-mark",
							children: "H"
						}), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", { children: "Hisense HireAI" }), /* @__PURE__ */ jsx("small", { children: "招聘运营智能体" })] })]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "pilot-badge",
						children: [/* @__PURE__ */ jsx("i", {}), " 黑客松演示环境"]
					}),
					/* @__PURE__ */ jsx("nav", {
						"aria-label": "主导航",
						children: navItems.map(([id, label, icon]) => /* @__PURE__ */ jsxs("button", {
							className: active === id ? "active" : "",
							onClick: () => setActive(id),
							children: [
								/* @__PURE__ */ jsx("span", { children: icon }),
								label,
								id === "jobs" && jobs.length > 0 && /* @__PURE__ */ jsx("em", { children: jobs.length })
							]
						}, id))
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "side-insight",
						children: [
							/* @__PURE__ */ jsx("span", { children: "本周 AI 提效" }),
							/* @__PURE__ */ jsx("strong", { children: "26.4h" }),
							/* @__PURE__ */ jsx("small", { children: "预计节省招聘工时" }),
							/* @__PURE__ */ jsx("div", { children: /* @__PURE__ */ jsx("i", { style: { width: "78%" } }) })
						]
					}),
					/* @__PURE__ */ jsxs("div", {
						className: "profile",
						children: [
							/* @__PURE__ */ jsx("span", { children: "HR" }),
							/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", { children: "招聘运营中心" }), /* @__PURE__ */ jsx("small", { children: "企业管理员" })] }),
							/* @__PURE__ */ jsx("button", {
								"aria-label": "更多选项",
								children: "•••"
							})
						]
					})
				]
			}),
			/* @__PURE__ */ jsxs("section", {
				className: "workspace",
				children: [
					/* @__PURE__ */ jsxs("header", {
						className: "topbar",
						children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("span", {
							className: "crumb",
							children: "海信容声广州公司 /"
						}), /* @__PURE__ */ jsx("b", { children: navItems.find((item) => item[0] === active)?.[1] })] }), /* @__PURE__ */ jsxs("div", {
							className: "top-actions",
							children: [/* @__PURE__ */ jsxs("button", {
								className: "icon-btn",
								"aria-label": "通知",
								children: ["♢", /* @__PURE__ */ jsx("i", {})]
							}), /* @__PURE__ */ jsx("button", {
								className: "primary",
								onClick: () => {
									setActive("jobs");
									notify("已打开岗位导入工作台");
								},
								children: "＋ 导入岗位数据"
							})]
						})]
					}),
					active === "dashboard" && /* @__PURE__ */ jsx(Dashboard, {
						allJobCount,
						duplicateRate,
						candidates,
						onNavigate: setActive
					}),
					active === "jobs" && /* @__PURE__ */ jsxs("section", {
						className: "page jobs-page",
						children: [/* @__PURE__ */ jsxs("div", {
							className: "page-heading",
							children: [/* @__PURE__ */ jsxs("div", { children: [
								/* @__PURE__ */ jsx("p", {
									className: "eyebrow",
									children: "JOB GOVERNANCE"
								}),
								/* @__PURE__ */ jsx("h1", { children: "岗位治理中心" }),
								/* @__PURE__ */ jsx("p", { children: "AI 已完成首轮清洗，已从飞书同步岗位数据，等待人工复核与治理。" })
							] }), /* @__PURE__ */ jsx("button", {
								className: "outline",
								onClick: () => notify("已生成岗位异常清单 CSV"),
								children: "导出治理报告"
							})]
						}), /* @__PURE__ */ jsxs("div", {
							className: "split-layout",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "panel job-list",
								children: [
									/* @__PURE__ */ jsxs("div", {
										className: "panel-tools",
										children: [/* @__PURE__ */ jsxs("label", { children: ["⌕", /* @__PURE__ */ jsx("input", {
											value: query,
											onChange: (e) => setQuery(e.target.value),
											placeholder: "搜索岗位或类型"
										})] }), /* @__PURE__ */ jsx("button", { children: "全部岗位⌄" })]
									}),
									/* @__PURE__ */ jsxs("div", {
										className: "list-head",
										children: [
											/* @__PURE__ */ jsx("span", { children: "岗位 / 工种" }),
											/* @__PURE__ */ jsx("span", { children: "薪资" }),
											/* @__PURE__ */ jsx("span", { children: "风险" })
										]
									}),
									filteredJobs.map((job) => /* @__PURE__ */ jsxs("button", {
										className: `job-row ${selectedJob.id === job.id ? "selected" : ""}`,
										onClick: () => setSelectedJob(job),
										children: [
											/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", { children: job.title }), /* @__PURE__ */ jsxs("small", { children: [
												job.type,
												" · ",
												job.location
											] })] }),
											/* @__PURE__ */ jsx("span", { children: job.salary }),
											/* @__PURE__ */ jsx("span", {
												className: `risk risk-${job.risk}`,
												children: job.risk
											})
										]
									}, job.id))
								]
							}), /* @__PURE__ */ jsx(JobWorkbench, {
								job: selectedJob,
								onApprove: approveJob,
								onNotify: notify
							})]
						})]
					}),
					active === "candidates" && /* @__PURE__ */ jsxs("section", {
						className: "page candidates-page",
						children: [
							/* @__PURE__ */ jsxs("div", {
								className: "page-heading",
								children: [/* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("p", {
										className: "eyebrow",
										children: "TALENT MATCHING"
									}),
									/* @__PURE__ */ jsx("h1", { children: "人才匹配工作台" }),
									/* @__PURE__ */ jsx("p", { children: "规则校验＋语义匹配＋人工终审，每个结论都有可追溯证据。" })
								] }), /* @__PURE__ */ jsxs("label", {
									className: "primary",
									style: { cursor: "pointer" },
									children: [uploading ? "解析中…" : "＋ 上传简历（投递即筛选）", /* @__PURE__ */ jsx("input", {
										type: "file",
										accept: ".pdf,.txt,.md,.docx",
										style: { display: "none" },
										onChange: onUploadCandidate
									})]
								})]
							}),
							/* @__PURE__ */ jsx("div", {
								className: "candidate-grid",
								children: candidates.map((candidate) => /* @__PURE__ */ jsxs("button", {
									className: `candidate-card ${selectedCandidate.id === candidate.id ? "selected" : ""}`,
									onClick: () => setSelectedCandidate(candidate),
									children: [
										/* @__PURE__ */ jsxs("div", {
											className: "candidate-top",
											children: [
												/* @__PURE__ */ jsx("span", {
													className: "avatar",
													children: candidate.initials
												}),
												/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", { children: candidate.name }), /* @__PURE__ */ jsx("small", { children: candidate.phone })] }),
												/* @__PURE__ */ jsxs("strong", { children: [candidate.score, /* @__PURE__ */ jsx("small", { children: "匹配分" })] })
											]
										}),
										/* @__PURE__ */ jsx("h3", { children: candidate.role }),
										/* @__PURE__ */ jsx("div", {
											className: "skill-row",
											children: candidate.skills.map((skill) => /* @__PURE__ */ jsx("span", { children: skill }, skill))
										}),
										/* @__PURE__ */ jsxs("div", {
											className: "card-foot",
											children: [/* @__PURE__ */ jsx("span", {
												className: `stage stage-${candidate.stage}`,
												children: candidate.stage
											}), /* @__PURE__ */ jsx("span", { children: "查看证据 →" })]
										})
									]
								}, candidate.id))
							}),
							/* @__PURE__ */ jsx(CandidateEvidence, {
								candidate: selectedCandidate,
								onSchedule: scheduleInterview
							})
						]
					}),
					active === "screening" && /* @__PURE__ */ jsxs(Fragment$1, { children: [/* @__PURE__ */ jsx(ResumeUpload, {}), /* @__PURE__ */ jsx(Screening, {
						candidate: selectedCandidate,
						step: screenStep,
						setStep: setScreenStep,
						onSchedule: scheduleInterview
					})] }),
					active === "interview" && /* @__PURE__ */ jsx(VideoInterview, {})
				]
			}),
			active === "evaluation" && /* @__PURE__ */ jsx(Evaluation, { notify }),
			toast && /* @__PURE__ */ jsxs("div", {
				className: "toast",
				children: [/* @__PURE__ */ jsx("span", { children: "✓" }), toast]
			})
		]
	});
}
function Dashboard({ allJobCount, duplicateRate, candidates, onNavigate }) {
	return /* @__PURE__ */ jsxs("section", {
		className: "page dashboard",
		children: [
			/* @__PURE__ */ jsxs("div", {
				className: "hero-row",
				children: [/* @__PURE__ */ jsxs("div", { children: [
					/* @__PURE__ */ jsx("p", {
						className: "eyebrow",
						children: "GOOD MORNING, RECRUITING TEAM"
					}),
					/* @__PURE__ */ jsx("h1", { children: "招聘全局，一屏掌握。" }),
					/* @__PURE__ */ jsxs("p", { children: [
						"AI 正在监控岗位质量与候选人转化，今天有 ",
						/* @__PURE__ */ jsx("b", { children: "7 项关键任务" }),
						"需要处理。"
					] })
				] }), /* @__PURE__ */ jsxs("div", {
					className: "ai-status",
					children: [
						/* @__PURE__ */ jsx("span", {
							className: "orb",
							children: "✦"
						}),
						/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", { children: "4 个智能体运行正常" }), /* @__PURE__ */ jsx("small", { children: "刚刚完成 16 次分析 · 0 项异常" })] }),
						/* @__PURE__ */ jsx("i", {})
					]
				})]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "metric-grid",
				children: [
					/* @__PURE__ */ jsxs("article", { children: [
						/* @__PURE__ */ jsx("span", { children: "有效岗位" }),
						/* @__PURE__ */ jsxs("strong", { children: [allJobCount, /* @__PURE__ */ jsx("small", { children: "条" })] }),
						/* @__PURE__ */ jsx("em", {
							className: "up",
							children: "↑ 12 本周新增"
						}),
						/* @__PURE__ */ jsx("i", {
							className: "metric-icon blue",
							children: "▦"
						})
					] }),
					/* @__PURE__ */ jsxs("article", { children: [
						/* @__PURE__ */ jsx("span", { children: "待处理候选人" }),
						/* @__PURE__ */ jsxs("strong", { children: [candidates.length, /* @__PURE__ */ jsx("small", { children: "人" })] }),
						/* @__PURE__ */ jsxs("em", { children: [
							"其中 ",
							candidates.filter((c) => c.score >= 80).length,
							" 人高匹配"
						] }),
						/* @__PURE__ */ jsx("i", {
							className: "metric-icon purple",
							children: "◎"
						})
					] }),
					/* @__PURE__ */ jsxs("article", { children: [
						/* @__PURE__ */ jsx("span", { children: "重复岗位率" }),
						/* @__PURE__ */ jsxs("strong", { children: [duplicateRate, /* @__PURE__ */ jsx("small", { children: "%" })] }),
						/* @__PURE__ */ jsx("em", {
							className: "down",
							children: "↓ 治理后预计 18%"
						}),
						/* @__PURE__ */ jsx("i", {
							className: "metric-icon amber",
							children: "⚠"
						})
					] }),
					/* @__PURE__ */ jsxs("article", { children: [
						/* @__PURE__ */ jsx("span", { children: "平均招聘周期" }),
						/* @__PURE__ */ jsxs("strong", { children: ["6.8", /* @__PURE__ */ jsx("small", { children: "天" })] }),
						/* @__PURE__ */ jsx("em", {
							className: "up",
							children: "↓ 2.4 天 AI 提效"
						}),
						/* @__PURE__ */ jsx("i", {
							className: "metric-icon green",
							children: "◷"
						})
					] })
				]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "dashboard-grid",
				children: [
					/* @__PURE__ */ jsxs("article", {
						className: "panel funnel",
						children: [/* @__PURE__ */ jsxs("div", {
							className: "panel-title",
							children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("p", {
								className: "eyebrow",
								children: "RECRUITMENT FUNNEL"
							}), /* @__PURE__ */ jsx("h2", { children: "招聘转化漏斗" })] }), /* @__PURE__ */ jsx("span", { children: "过去 30 天⌄" })]
						}), /* @__PURE__ */ jsxs("div", {
							className: "funnel-chart",
							children: [
								/* @__PURE__ */ jsxs("div", {
									style: { width: "100%" },
									children: [
										/* @__PURE__ */ jsx("span", { children: "简历进入" }),
										/* @__PURE__ */ jsx("b", { children: "326" }),
										/* @__PURE__ */ jsx("small", { children: "100%" })
									]
								}),
								/* @__PURE__ */ jsxs("div", {
									style: { width: "82%" },
									children: [
										/* @__PURE__ */ jsx("span", { children: "AI 初筛" }),
										/* @__PURE__ */ jsx("b", { children: "218" }),
										/* @__PURE__ */ jsx("small", { children: "66.9%" })
									]
								}),
								/* @__PURE__ */ jsxs("div", {
									style: { width: "61%" },
									children: [
										/* @__PURE__ */ jsx("span", { children: "人工复核" }),
										/* @__PURE__ */ jsx("b", { children: "128" }),
										/* @__PURE__ */ jsx("small", { children: "39.3%" })
									]
								}),
								/* @__PURE__ */ jsxs("div", {
									style: { width: "43%" },
									children: [
										/* @__PURE__ */ jsx("span", { children: "安排面试" }),
										/* @__PURE__ */ jsx("b", { children: "74" }),
										/* @__PURE__ */ jsx("small", { children: "22.7%" })
									]
								}),
								/* @__PURE__ */ jsxs("div", {
									style: { width: "25%" },
									children: [
										/* @__PURE__ */ jsx("span", { children: "确认录用" }),
										/* @__PURE__ */ jsx("b", { children: "31" }),
										/* @__PURE__ */ jsx("small", { children: "9.5%" })
									]
								})
							]
						})]
					}),
					/* @__PURE__ */ jsxs("article", {
						className: "panel actions",
						children: [
							/* @__PURE__ */ jsxs("div", {
								className: "panel-title",
								children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("p", {
									className: "eyebrow",
									children: "ACTION CENTER"
								}), /* @__PURE__ */ jsx("h2", { children: "今日行动中心" })] }), /* @__PURE__ */ jsx("button", {
									onClick: () => onNavigate("jobs"),
									children: "查看全部 →"
								})]
							}),
							/* @__PURE__ */ jsxs("button", {
								onClick: () => onNavigate("jobs"),
								children: [
									/* @__PURE__ */ jsx("span", {
										className: "action-icon red",
										children: "!"
									}),
									/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", { children: "23 项岗位风险待复核" }), /* @__PURE__ */ jsx("small", { children: "含年龄限制、薪资冲突与标题残缺" })] }),
									/* @__PURE__ */ jsx("em", { children: "高优先级" })
								]
							}),
							/* @__PURE__ */ jsxs("button", {
								onClick: () => onNavigate("candidates"),
								children: [
									/* @__PURE__ */ jsx("span", {
										className: "action-icon purple",
										children: "◎"
									}),
									/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", { children: "15 位高匹配候选人" }), /* @__PURE__ */ jsx("small", { children: "建议今日完成首次联系" })] }),
									/* @__PURE__ */ jsx("em", { children: "人才匹配" })
								]
							}),
							/* @__PURE__ */ jsxs("button", {
								onClick: () => onNavigate("screening"),
								children: [
									/* @__PURE__ */ jsx("span", {
										className: "action-icon blue",
										children: "◇"
									}),
									/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", { children: "8 场 AI 初筛已完成" }), /* @__PURE__ */ jsx("small", { children: "摘要与证据等待人工终审" })] }),
									/* @__PURE__ */ jsx("em", { children: "待审核" })
								]
							})
						]
					}),
					/* @__PURE__ */ jsxs("article", {
						className: "panel agent-feed",
						children: [
							/* @__PURE__ */ jsxs("div", {
								className: "panel-title",
								children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("p", {
									className: "eyebrow",
									children: "AGENT ACTIVITY"
								}), /* @__PURE__ */ jsx("h2", { children: "智能体实时动态" })] }), /* @__PURE__ */ jsxs("span", {
									className: "live",
									children: [/* @__PURE__ */ jsx("i", {}), " LIVE"]
								})]
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "feed-item",
								children: [/* @__PURE__ */ jsx("span", { children: "治" }), /* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("b", { children: "岗位治理智能体" }),
									/* @__PURE__ */ jsx("p", { children: "合并 17 条“容桂装配工”重复信息，发现 3 项薪资冲突。" }),
									/* @__PURE__ */ jsx("small", { children: "2 分钟前" })
								] })]
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "feed-item",
								children: [/* @__PURE__ */ jsx("span", { children: "配" }), /* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("b", { children: "人才匹配智能体" }),
									/* @__PURE__ */ jsx("p", { children: "完成陈浩与“设备维修工程师”的证据化匹配，得分 92。" }),
									/* @__PURE__ */ jsx("small", { children: "6 分钟前" })
								] })]
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "feed-item",
								children: [/* @__PURE__ */ jsx("span", { children: "筛" }), /* @__PURE__ */ jsxs("div", { children: [
									/* @__PURE__ */ jsx("b", { children: "AI 初筛智能体" }),
									/* @__PURE__ */ jsx("p", { children: "李敏已完成 5 个必要问题，夜班意愿需人工确认。" }),
									/* @__PURE__ */ jsx("small", { children: "11 分钟前" })
								] })]
							})
						]
					}),
					/* @__PURE__ */ jsxs("article", {
						className: "panel efficiency",
						children: [
							/* @__PURE__ */ jsxs("div", {
								className: "panel-title",
								children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("p", {
									className: "eyebrow",
									children: "EFFICIENCY"
								}), /* @__PURE__ */ jsx("h2", { children: "AI 提效价值" })] }), /* @__PURE__ */ jsx("span", { children: "本周" })]
							}),
							/* @__PURE__ */ jsx("div", {
								className: "efficiency-ring",
								children: /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("strong", { children: "26.4" }), /* @__PURE__ */ jsx("small", { children: "节省工时" })] })
							}),
							/* @__PURE__ */ jsxs("div", {
								className: "efficiency-list",
								children: [
									/* @__PURE__ */ jsxs("p", { children: [/* @__PURE__ */ jsx("span", { children: "岗位整理" }), /* @__PURE__ */ jsx("b", { children: "11.2h" })] }),
									/* @__PURE__ */ jsxs("p", { children: [/* @__PURE__ */ jsx("span", { children: "简历初筛" }), /* @__PURE__ */ jsx("b", { children: "9.6h" })] }),
									/* @__PURE__ */ jsxs("p", { children: [/* @__PURE__ */ jsx("span", { children: "沟通与报告" }), /* @__PURE__ */ jsx("b", { children: "5.6h" })] })
								]
							})
						]
					})
				]
			})
		]
	});
}
function JobWorkbench({ job, onApprove, onNotify }) {
	const [jdOpen, setJdOpen] = useState(false);
	return /* @__PURE__ */ jsxs("article", {
		className: "panel job-workbench",
		children: [
			/* @__PURE__ */ jsxs("div", {
				className: "workbench-head",
				children: [/* @__PURE__ */ jsxs("div", { children: [
					/* @__PURE__ */ jsxs("span", {
						className: `risk risk-${job.risk}`,
						children: [job.risk, "风险"]
					}),
					/* @__PURE__ */ jsx("h2", { children: job.title }),
					/* @__PURE__ */ jsxs("p", { children: [
						"编号 HS-GZ-",
						String(job.id).padStart(3, "0"),
						" · ",
						job.status
					] })
				] }), /* @__PURE__ */ jsx("button", {
					"aria-label": "更多",
					children: "•••"
				})]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "compare-label",
				children: [/* @__PURE__ */ jsx("span", { children: "原始 OCR 文案" }), /* @__PURE__ */ jsx("span", { children: "AI 标准化岗位画像" })]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "compare",
				children: [/* @__PURE__ */ jsxs("div", {
					className: "raw-copy",
					children: [/* @__PURE__ */ jsxs("p", { children: [
						job.title,
						" 佛山 ",
						job.experience,
						" 职位描述：包吃住 / 工资 ",
						job.salary,
						" / 立即沟通，工作简单易上手，具体以现场安排为准。"
					] }), /* @__PURE__ */ jsx("span", { children: "来源：BOSS 公开页面截图 OCR" })]
				}), /* @__PURE__ */ jsxs("div", {
					className: "clean-copy",
					children: [/* @__PURE__ */ jsx("h3", { children: job.title }), /* @__PURE__ */ jsxs("dl", { children: [
						/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", { children: "岗位类别" }), /* @__PURE__ */ jsx("dd", { children: job.type })] }),
						/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", { children: "工作地点" }), /* @__PURE__ */ jsxs("dd", { children: [job.location, " · 容桂园区"] })] }),
						/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", { children: "薪资范围" }), /* @__PURE__ */ jsx("dd", { children: job.salary })] }),
						/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", { children: "经验 / 学历" }), /* @__PURE__ */ jsxs("dd", { children: [
							job.experience,
							" / ",
							job.education
						] })] }),
						/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", { children: "用工性质" }), /* @__PURE__ */ jsx("dd", { children: job.type.includes("临时") ? "临时用工" : "正式用工" })] }),
						/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", { children: "班次" }), /* @__PURE__ */ jsx("dd", { children: "两班倒 · 月休 4 天" })] })
					] })]
				})]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "risk-box",
				children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("span", { children: "⚠" }), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", { children: "AI 合规与质量检查" }), /* @__PURE__ */ jsx("p", { children: "发现原文职责不完整、薪资口径需确认；涉及年龄或个人条件时不得作为 AI 自动淘汰依据。" })] })] }), /* @__PURE__ */ jsx("em", { children: "需人工复核" })]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "rationale",
				children: [
					/* @__PURE__ */ jsx("b", { children: "本次优化依据" }),
					/* @__PURE__ */ jsx("span", { children: "统一岗位命名" }),
					/* @__PURE__ */ jsx("span", { children: "结构化薪资" }),
					/* @__PURE__ */ jsx("span", { children: "补全班次信息" }),
					/* @__PURE__ */ jsx("span", { children: "移除歧视性表达" })
				]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "workbench-actions",
				children: [/* @__PURE__ */ jsx("button", {
					className: "outline",
					onClick: () => setJdOpen(true),
					children: "✎ 生成 / 编辑 JD"
				}), /* @__PURE__ */ jsx("button", {
					className: "primary",
					onClick: onApprove,
					children: "✓ 人工确认并发布"
				})]
			}),
			jdOpen && /* @__PURE__ */ jsx(JdEditor, {
				jobTitle: job.title,
				onClose: () => setJdOpen(false),
				onSaved: (m) => onNotify(m)
			})
		]
	});
}
function CandidateEvidence({ candidate, onSchedule }) {
	return /* @__PURE__ */ jsxs("article", {
		className: "panel evidence-panel",
		children: [/* @__PURE__ */ jsxs("div", {
			className: "evidence-score",
			children: [
				/* @__PURE__ */ jsxs("div", {
					className: "score-ring",
					children: [/* @__PURE__ */ jsx("span", { children: candidate.score }), /* @__PURE__ */ jsx("small", { children: "/ 100" })]
				}),
				/* @__PURE__ */ jsxs("div", { children: [
					/* @__PURE__ */ jsx("p", {
						className: "eyebrow",
						children: "EXPLAINABLE MATCH"
					}),
					/* @__PURE__ */ jsxs("h2", { children: [
						candidate.name,
						" × ",
						candidate.role
					] }),
					/* @__PURE__ */ jsx("p", { children: "综合硬条件、经历相关度与到岗可行性；最终决定需人工确认。" })
				] }),
				/* @__PURE__ */ jsx("button", {
					className: "primary",
					onClick: onSchedule,
					children: "安排面试"
				})
			]
		}), /* @__PURE__ */ jsxs("div", {
			className: "evidence-grid",
			children: [
				/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("h3", { children: "匹配证据" }), candidate.evidence.map((item) => /* @__PURE__ */ jsxs("p", { children: [/* @__PURE__ */ jsx("span", { children: "✓" }), item] }, item))] }),
				/* @__PURE__ */ jsxs("div", { children: [
					/* @__PURE__ */ jsx("h3", { children: "待确认缺口" }),
					/* @__PURE__ */ jsxs("p", {
						className: "gap",
						children: [/* @__PURE__ */ jsx("span", { children: "!" }), candidate.gap]
					}),
					/* @__PURE__ */ jsxs("p", {
						className: "gap",
						children: [/* @__PURE__ */ jsx("span", { children: "!" }), "请核验证书原件与有效期"]
					})
				] }),
				/* @__PURE__ */ jsxs("div", { children: [
					/* @__PURE__ */ jsx("h3", { children: "评分构成" }),
					/* @__PURE__ */ jsxs("p", { children: [/* @__PURE__ */ jsx("span", { children: "硬条件" }), /* @__PURE__ */ jsx("b", { children: "36 / 40" })] }),
					/* @__PURE__ */ jsxs("p", { children: [/* @__PURE__ */ jsx("span", { children: "技能经历" }), /* @__PURE__ */ jsx("b", { children: "32 / 35" })] }),
					/* @__PURE__ */ jsxs("p", { children: [/* @__PURE__ */ jsx("span", { children: "到岗适配" }), /* @__PURE__ */ jsx("b", { children: "24 / 25" })] })
				] })
			]
		})]
	});
}
var FAMILY_OPTIONS = [
	["firstline", "一线生产"],
	["process-equipment", "工艺 / 设备"],
	["quality", "质量 / 检验"],
	["procurement-logistics", "采购 / 物流"],
	["production-management", "现场管理"]
];
function ResumeUpload() {
	const [text, setText] = useState("");
	const [jobName, setJobName] = useState("装配包装工");
	const [family, setFamily] = useState("firstline");
	const [res, setRes] = useState(null);
	const [busy, setBusy] = useState(false);
	const samples = {
		firstline: "姓名：刘芳。大专，电子专业，3年装配经验，有电工证，接受倒班，一个月内到岗。",
		"process-equipment": "姓名：陈浩。本科，机械制造专业，5 年设备维修经验，持有电工证、钳工证，接受倒班，随时到岗。"
	};
	const run = async () => {
		if (!text.trim()) return;
		setBusy(true);
		setRes(await screenResume(text, jobName, family).catch(() => null));
		setBusy(false);
	};
	const onFile = async (e) => {
		const f = e.target.files?.[0];
		if (!f) return;
		setBusy(true);
		setRes(await uploadResume(f, jobName, family).catch(() => null));
		setBusy(false);
		e.target.value = "";
	};
	return /* @__PURE__ */ jsxs("section", {
		className: "panel",
		style: {
			marginBottom: 18,
			padding: 18
		},
		children: [
			/* @__PURE__ */ jsxs("div", {
				style: {
					display: "flex",
					justifyContent: "space-between",
					alignItems: "center",
					marginBottom: 12
				},
				children: [/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("p", {
					className: "eyebrow",
					children: "RESUME UPLOAD"
				}), /* @__PURE__ */ jsx("h2", {
					style: { margin: 0 },
					children: "上传即打分"
				})] }), /* @__PURE__ */ jsxs("div", {
					style: {
						display: "flex",
						gap: 8
					},
					children: [/* @__PURE__ */ jsx("button", {
						className: "outline",
						onClick: () => setText(samples.firstline),
						children: "示例·一线"
					}), /* @__PURE__ */ jsx("button", {
						className: "outline",
						onClick: () => setText(samples["process-equipment"]),
						children: "示例·设备"
					})]
				})]
			}),
			/* @__PURE__ */ jsx("textarea", {
				value: text,
				onChange: (e) => setText(e.target.value),
				placeholder: "粘贴简历文本…",
				rows: 4,
				style: {
					width: "100%",
					border: "1px solid var(--line)",
					borderRadius: 10,
					padding: 12,
					resize: "vertical"
				}
			}),
			/* @__PURE__ */ jsxs("div", {
				style: {
					display: "flex",
					gap: 10,
					marginTop: 10,
					flexWrap: "wrap",
					alignItems: "center"
				},
				children: [
					/* @__PURE__ */ jsx("input", {
						value: jobName,
						onChange: (e) => setJobName(e.target.value),
						placeholder: "岗位名",
						style: {
							border: "1px solid var(--line)",
							borderRadius: 8,
							padding: "8px 10px"
						}
					}),
					/* @__PURE__ */ jsx("select", {
						value: family,
						onChange: (e) => setFamily(e.target.value),
						style: {
							border: "1px solid var(--line)",
							borderRadius: 8,
							padding: "8px 10px"
						},
						children: FAMILY_OPTIONS.map(([k, l]) => /* @__PURE__ */ jsx("option", {
							value: k,
							children: l
						}, k))
					}),
					/* @__PURE__ */ jsxs("label", {
						className: "outline",
						style: { cursor: "pointer" },
						children: [busy ? "解析中…" : "📎 上传简历文件", /* @__PURE__ */ jsx("input", {
							type: "file",
							accept: ".pdf,.txt,.md,.docx",
							style: { display: "none" },
							onChange: onFile
						})]
					}),
					/* @__PURE__ */ jsx("button", {
						className: "primary",
						disabled: busy,
						onClick: run,
						children: busy ? "打分中…" : "开始打分"
					})
				]
			}),
			res && res.success && /* @__PURE__ */ jsxs("div", {
				style: {
					marginTop: 14,
					background: "#f7faff",
					border: "1px solid #dbe7ff",
					borderRadius: 10,
					padding: 14
				},
				children: [/* @__PURE__ */ jsxs("div", {
					style: {
						display: "flex",
						gap: 18,
						flexWrap: "wrap"
					},
					children: [
						/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", {
							style: { fontSize: 22 },
							children: res.result?.匹配度
						}), /* @__PURE__ */ jsx("small", { children: " / 100 匹配度" })] }),
						/* @__PURE__ */ jsxs("div", { children: ["等级：", /* @__PURE__ */ jsx("b", { children: res.result?.等级 })] }),
						/* @__PURE__ */ jsxs("div", { children: ["风险：", /* @__PURE__ */ jsx("b", { children: res.result?.风险等级 })] }),
						/* @__PURE__ */ jsxs("div", { children: ["入池：", res.talent_pool?.pooled ? "已入人才池 " + res.talent_pool?.candidate_id : "未入池"] })
					]
				}), /* @__PURE__ */ jsxs("p", {
					style: {
						margin: "10px 0 0",
						color: "var(--muted)"
					},
					children: ["匹配总结：", res.result?.匹配总结]
				})]
			}),
			res && !res.success && /* @__PURE__ */ jsx("p", {
				style: {
					color: "var(--red)",
					marginTop: 10
				},
				children: res.error
			})
		]
	});
}
function Evaluation({ notify }) {
	const [rows, setRows] = useState([]);
	const [fallback, setFallback] = useState(null);
	const [decisions, setDecisions] = useState([]);
	const [reviewFor, setReviewFor] = useState(null);
	const [reviewDecision, setReviewDecision] = useState("通过");
	const [reviewNote, setReviewNote] = useState("");
	const load = async () => {
		try {
			setRows(await fetchTalentPool());
		} catch {}
		try {
			setDecisions(await fetchDecisions());
		} catch {}
	};
	useEffect(() => {
		load();
	}, []);
	const onSeed = async () => {
		await seedDemo().catch(() => void 0);
		notify("已载入 6 份演示候选人");
		load();
	};
	const onFallback = async (row) => {
		const r = await offerFallback(row.jobFamily, row.candidateId).catch(() => null);
		if (r && r.success) {
			setFallback(r);
			notify("已触发 Offer 递补");
			load();
		}
	};
	const onPush = async (row) => {
		const r = await departmentPush({
			candidate_id: row.candidateId,
			name: row.name,
			job_family: row.jobFamily
		}).catch(() => null);
		if (r && r.success) {
			notify("已推送用人部门复核");
			load();
		} else if (r) notify("推送失败：" + (r.error || "未知"));
	};
	const onReview = async (row) => {
		const r = await submitDepartmentDecision({
			candidate_id: row.candidateId,
			name: row.name,
			job_family: row.jobFamily,
			decision: reviewDecision,
			note: reviewNote
		}).catch(() => null);
		if (r && r.success) {
			notify(r.message || "已记录复核");
			setReviewFor(null);
			setReviewNote("");
			load();
		}
	};
	return /* @__PURE__ */ jsxs("section", {
		className: "page evaluation-page",
		children: [
			/* @__PURE__ */ jsxs("div", {
				className: "page-heading",
				children: [/* @__PURE__ */ jsxs("div", { children: [
					/* @__PURE__ */ jsx("p", {
						className: "eyebrow",
						children: "TALENT EVALUATION"
					}),
					/* @__PURE__ */ jsx("h1", { children: "人才评价汇总" }),
					/* @__PURE__ */ jsx("p", { children: "合格候选人自动入库、分类标签、横向对比；选定者放弃 Offer 时按匹配度秒级递补下一顺位。" })
				] }), /* @__PURE__ */ jsx("button", {
					className: "primary",
					onClick: onSeed,
					children: "⟳ 载入演示数据"
				})]
			}),
			fallback && /* @__PURE__ */ jsxs("div", {
				style: {
					background: "#eafaf2",
					border: "1px solid #b7e6cf",
					borderRadius: 12,
					padding: 14,
					marginBottom: 14
				},
				children: [
					/* @__PURE__ */ jsx("b", { children: "Offer 递补结果" }),
					/* @__PURE__ */ jsx("p", {
						style: { margin: "6px 0" },
						children: fallback.fallback_reason
					}),
					fallback.next_best && /* @__PURE__ */ jsxs("span", {
						style: { color: "var(--green)" },
						children: [
							"→ 推进：",
							fallback.next_best.name,
							"（",
							fallback.next_best.totalScore,
							"分 / ",
							fallback.next_best.grade,
							"）"
						]
					})
				]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "panel",
				style: {
					padding: 0,
					overflow: "hidden"
				},
				children: [/* @__PURE__ */ jsxs("table", {
					style: {
						width: "100%",
						borderCollapse: "collapse",
						fontSize: 13
					},
					children: [/* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", {
						style: {
							background: "#f4f6fa",
							textAlign: "left"
						},
						children: [
							/* @__PURE__ */ jsx("th", {
								style: th,
								children: "候选人"
							}),
							/* @__PURE__ */ jsx("th", {
								style: th,
								children: "岗位"
							}),
							/* @__PURE__ */ jsx("th", {
								style: th,
								children: "匹配度"
							}),
							/* @__PURE__ */ jsx("th", {
								style: th,
								children: "等级"
							}),
							/* @__PURE__ */ jsx("th", {
								style: th,
								children: "风险"
							}),
							/* @__PURE__ */ jsx("th", {
								style: th,
								children: "标签"
							}),
							/* @__PURE__ */ jsx("th", {
								style: th,
								children: "状态"
							}),
							/* @__PURE__ */ jsx("th", {
								style: th,
								children: "操作"
							})
						]
					}) }), /* @__PURE__ */ jsx("tbody", { children: rows.map((row) => /* @__PURE__ */ jsxs("tr", {
						style: { borderTop: "1px solid var(--line)" },
						children: [
							/* @__PURE__ */ jsx("td", {
								style: td,
								children: /* @__PURE__ */ jsx("b", { children: row.name })
							}),
							/* @__PURE__ */ jsx("td", {
								style: td,
								children: row.jobName
							}),
							/* @__PURE__ */ jsx("td", {
								style: td,
								children: /* @__PURE__ */ jsx("b", { children: row.totalScore })
							}),
							/* @__PURE__ */ jsx("td", {
								style: td,
								children: row.grade
							}),
							/* @__PURE__ */ jsx("td", {
								style: td,
								children: /* @__PURE__ */ jsx("span", {
									className: `risk risk-${row.riskLevel}`,
									children: row.riskLevel
								})
							}),
							/* @__PURE__ */ jsx("td", {
								style: td,
								children: (row.tags || []).join("、")
							}),
							/* @__PURE__ */ jsx("td", {
								style: td,
								children: row.status
							}),
							/* @__PURE__ */ jsxs("td", {
								style: td,
								children: [
									/* @__PURE__ */ jsx("button", {
										className: "outline",
										style: {
											marginRight: 6,
											padding: "4px 8px"
										},
										onClick: () => onPush(row),
										children: "推送给用人部门"
									}),
									/* @__PURE__ */ jsx("button", {
										className: "outline",
										style: {
											marginRight: 6,
											padding: "4px 8px"
										},
										onClick: () => onFallback(row),
										children: "放弃Offer递补"
									}),
									/* @__PURE__ */ jsx("button", {
										className: "outline",
										style: { padding: "4px 8px" },
										onClick: () => setReviewFor(row.candidateId),
										children: "部门复核"
									})
								]
							})
						]
					}, row.candidateId)) })]
				}), !rows.length && /* @__PURE__ */ jsx("p", {
					style: {
						padding: 18,
						color: "var(--muted)"
					},
					children: "暂无数据，点击右上角「载入演示数据」。"
				})]
			}),
			reviewFor && /* @__PURE__ */ jsxs("div", {
				className: "panel",
				style: {
					marginTop: 14,
					padding: 16
				},
				children: [/* @__PURE__ */ jsx("h3", {
					style: { marginTop: 0 },
					children: "用人部门复核"
				}), /* @__PURE__ */ jsxs("div", {
					style: {
						display: "flex",
						gap: 10,
						flexWrap: "wrap",
						alignItems: "center"
					},
					children: [
						/* @__PURE__ */ jsxs("select", {
							value: reviewDecision,
							onChange: (e) => setReviewDecision(e.target.value),
							style: {
								border: "1px solid var(--line)",
								borderRadius: 8,
								padding: "8px 10px"
							},
							children: [/* @__PURE__ */ jsx("option", {
								value: "通过",
								children: "通过"
							}), /* @__PURE__ */ jsx("option", {
								value: "不通过",
								children: "不通过"
							})]
						}),
						/* @__PURE__ */ jsx("input", {
							value: reviewNote,
							onChange: (e) => setReviewNote(e.target.value),
							placeholder: "备注（选填）",
							style: {
								border: "1px solid var(--line)",
								borderRadius: 8,
								padding: "8px 10px",
								minWidth: 220
							}
						}),
						/* @__PURE__ */ jsx("button", {
							className: "primary",
							onClick: () => {
								const r = rows.find((x) => x.candidateId === reviewFor);
								if (r) onReview(r);
							},
							children: "提交并推送 HR"
						}),
						/* @__PURE__ */ jsx("button", {
							className: "outline",
							onClick: () => setReviewFor(null),
							children: "取消"
						})
					]
				})]
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "panel",
				style: {
					marginTop: 14,
					padding: 16
				},
				children: [
					/* @__PURE__ */ jsxs("h3", {
						style: { marginTop: 0 },
						children: [
							"用人部门复核记录（",
							decisions.length,
							"）"
						]
					}),
					decisions.map((d, i) => /* @__PURE__ */ jsxs("div", {
						style: {
							display: "flex",
							gap: 10,
							padding: "8px 0",
							borderTop: i ? "1px solid var(--line)" : "none",
							fontSize: 13
						},
						children: [
							/* @__PURE__ */ jsx("b", { children: String(d.name) }),
							/* @__PURE__ */ jsx("span", {
								style: { color: d.decision === "通过" ? "var(--green)" : "var(--red)" },
								children: String(d.decision)
							}),
							/* @__PURE__ */ jsx("span", {
								style: { color: "var(--muted)" },
								children: String(d.note || "无备注")
							}),
							/* @__PURE__ */ jsx("small", {
								style: {
									marginLeft: "auto",
									color: "var(--muted)"
								},
								children: String(d.at)
							})
						]
					}, i)),
					!decisions.length && /* @__PURE__ */ jsx("p", {
						style: { color: "var(--muted)" },
						children: "暂无复核记录。"
					})
				]
			})
		]
	});
}
function JdEditor({ jobTitle, onClose, onSaved }) {
	const [family, setFamily] = useState("firstline");
	const [position, setPosition] = useState(jobTitle || "装配包装工");
	const [location, setLocation] = useState("佛山顺德");
	const [salary, setSalary] = useState("5000-6000元/月");
	const [extraHard, setExtraHard] = useState("");
	const [extraSkills, setExtraSkills] = useState("");
	const [jd, setJd] = useState(null);
	const [saved, setSaved] = useState(false);
	const buildParams = () => {
		const p = {
			position,
			location,
			salary
		};
		if (extraHard) p.extra_hard = extraHard.split(/[，,、]/).map((s) => s.trim()).filter(Boolean);
		if (extraSkills) p.extra_skills = extraSkills.split(/[，,、]/).map((s) => s.trim()).filter(Boolean);
		return p;
	};
	const gen = async () => {
		const r = await generateJd(family, buildParams()).catch(() => null);
		if (r && r.success) setJd(r.jd);
	};
	const save = async () => {
		const r = await saveJd(family, buildParams()).catch(() => null);
		if (r && r.success) {
			setSaved(true);
			onSaved("JD 已保存并写回飞书招聘需求表");
		} else if (r) onSaved("JD 保存失败：" + (r.error || "未知"));
	};
	return /* @__PURE__ */ jsx("div", {
		onClick: onClose,
		style: {
			position: "fixed",
			inset: 0,
			background: "rgba(8,16,29,.5)",
			display: "flex",
			alignItems: "center",
			justifyContent: "center",
			zIndex: 50,
			padding: 16
		},
		children: /* @__PURE__ */ jsxs("div", {
			onClick: (e) => e.stopPropagation(),
			className: "panel",
			style: {
				maxWidth: 560,
				width: "100%",
				maxHeight: "90vh",
				overflow: "auto",
				padding: 20
			},
			children: [
				/* @__PURE__ */ jsxs("div", {
					style: {
						display: "flex",
						justifyContent: "space-between",
						alignItems: "center"
					},
					children: [/* @__PURE__ */ jsx("h2", {
						style: { margin: 0 },
						children: "生成 / 编辑 JD"
					}), /* @__PURE__ */ jsx("button", {
						className: "outline",
						onClick: onClose,
						children: "关闭"
					})]
				}),
				/* @__PURE__ */ jsxs("div", {
					style: {
						display: "grid",
						gap: 10,
						marginTop: 14
					},
					children: [
						/* @__PURE__ */ jsxs("label", {
							style: lbl,
							children: ["岗位族", /* @__PURE__ */ jsxs("select", {
								value: family,
								onChange: (e) => setFamily(e.target.value),
								style: inp,
								children: [
									/* @__PURE__ */ jsx("option", {
										value: "firstline",
										children: "一线生产"
									}),
									/* @__PURE__ */ jsx("option", {
										value: "process-equipment",
										children: "工艺 / 设备"
									}),
									/* @__PURE__ */ jsx("option", {
										value: "quality",
										children: "质量 / 检验"
									}),
									/* @__PURE__ */ jsx("option", {
										value: "procurement-logistics",
										children: "采购 / 物流"
									}),
									/* @__PURE__ */ jsx("option", {
										value: "production-management",
										children: "现场管理"
									})
								]
							})]
						}),
						/* @__PURE__ */ jsxs("label", {
							style: lbl,
							children: ["岗位名称", /* @__PURE__ */ jsx("input", {
								value: position,
								onChange: (e) => setPosition(e.target.value),
								style: inp
							})]
						}),
						/* @__PURE__ */ jsxs("label", {
							style: lbl,
							children: ["工作地点", /* @__PURE__ */ jsx("input", {
								value: location,
								onChange: (e) => setLocation(e.target.value),
								style: inp
							})]
						}),
						/* @__PURE__ */ jsxs("label", {
							style: lbl,
							children: ["薪资", /* @__PURE__ */ jsx("input", {
								value: salary,
								onChange: (e) => setSalary(e.target.value),
								style: inp
							})]
						}),
						/* @__PURE__ */ jsxs("label", {
							style: lbl,
							children: ["补充硬条件（逗号分隔）", /* @__PURE__ */ jsx("input", {
								value: extraHard,
								onChange: (e) => setExtraHard(e.target.value),
								style: inp,
								placeholder: "如：需高处作业证"
							})]
						}),
						/* @__PURE__ */ jsxs("label", {
							style: lbl,
							children: ["补充技能（逗号分隔）", /* @__PURE__ */ jsx("input", {
								value: extraSkills,
								onChange: (e) => setExtraSkills(e.target.value),
								style: inp,
								placeholder: "如：PLC、焊接"
							})]
						})
					]
				}),
				/* @__PURE__ */ jsxs("div", {
					style: {
						display: "flex",
						gap: 8,
						marginTop: 14
					},
					children: [
						/* @__PURE__ */ jsx("button", {
							className: "primary",
							onClick: gen,
							children: "生成 JD"
						}),
						/* @__PURE__ */ jsx("button", {
							className: "outline",
							onClick: save,
							children: "保存（写回飞书）"
						}),
						saved && /* @__PURE__ */ jsx("span", {
							style: {
								color: "var(--green)",
								alignSelf: "center"
							},
							children: "已保存 ✓"
						})
					]
				}),
				jd && /* @__PURE__ */ jsx("pre", {
					style: {
						background: "#0e182a",
						color: "#cfe3ff",
						borderRadius: 10,
						padding: 14,
						marginTop: 14,
						fontSize: 12,
						overflow: "auto"
					},
					children: JSON.stringify(jd, null, 2)
				})
			]
		})
	});
}
var th = {
	padding: "10px 12px",
	fontWeight: 600,
	color: "var(--muted)"
};
var td = { padding: "10px 12px" };
var lbl = {
	display: "grid",
	gap: 4,
	fontSize: 12,
	color: "var(--muted)"
};
var inp = {
	border: "1px solid var(--line)",
	borderRadius: 8,
	padding: "8px 10px",
	fontSize: 14,
	color: "var(--ink)"
};
function Screening({ candidate, step, setStep, onSchedule }) {
	const [questions, setQuestions] = useState([]);
	const [answers, setAnswers] = useState({});
	const [assessment, setAssessment] = useState("");
	useEffect(() => {
		setStep(0);
		setAnswers({});
		fetchInterviewQuestions(candidate.name, assessment).then((d) => {
			if (d.questions?.length) setQuestions(d.questions);
		}).catch(() => void 0);
	}, [candidate.name, assessment]);
	const total = questions.length || 0;
	const current = questions[step - 1];
	const answer = (value) => {
		if (current) setAnswers((cur) => ({
			...cur,
			[current.id]: value
		}));
		setStep(step + 1);
	};
	const finish = async () => {
		await submitInterview(candidate.name, candidate.role, answers).catch(() => void 0);
		onSchedule();
	};
	return /* @__PURE__ */ jsxs("section", {
		className: "page screening-page",
		children: [
			/* @__PURE__ */ jsxs("div", {
				className: "page-heading",
				children: [/* @__PURE__ */ jsxs("div", { children: [
					/* @__PURE__ */ jsx("p", {
						className: "eyebrow",
						children: "AI SCREENING"
					}),
					/* @__PURE__ */ jsx("h1", { children: "结构化 AI 初筛" }),
					/* @__PURE__ */ jsx("p", { children: "只询问岗位必要信息，敏感问题自动拦截，所有结论等待人工终审。" })
				] }), /* @__PURE__ */ jsx("span", {
					className: "privacy-chip",
					children: "盾 隐私脱敏已开启"
				})]
			}),
			/* @__PURE__ */ jsx("div", {
				style: { marginBottom: 14 },
				children: /* @__PURE__ */ jsxs("label", {
					style: lbl,
					children: ["候选人测评报告（可选，粘贴后系统据此生成个性化追问）", /* @__PURE__ */ jsx("textarea", {
						value: assessment,
						onChange: (e) => setAssessment(e.target.value),
						placeholder: "如：逻辑思维 75 分（待提升）；团队协作 88 分",
						style: {
							...inp,
							minHeight: 56,
							resize: "vertical"
						}
					})]
				})
			}),
			/* @__PURE__ */ jsxs("div", {
				className: "screen-layout",
				children: [/* @__PURE__ */ jsxs("article", {
					className: "panel conversation",
					children: [
						/* @__PURE__ */ jsxs("div", {
							className: "conversation-head",
							children: [
								/* @__PURE__ */ jsx("span", {
									className: "avatar",
									children: candidate.initials
								}),
								/* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("b", { children: candidate.name }), /* @__PURE__ */ jsxs("small", { children: [
									candidate.role,
									" · 匹配分 ",
									candidate.score
								] })] }),
								/* @__PURE__ */ jsxs("span", {
									className: "live",
									children: [/* @__PURE__ */ jsx("i", {}), " AI 初筛中"]
								})
							]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "messages",
							children: [/* @__PURE__ */ jsxs("div", {
								className: "message ai",
								children: [/* @__PURE__ */ jsx("span", { children: "AI" }), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsxs("p", { children: [
									"你好，",
									candidate.name.slice(0, 1),
									"先生。接下来有 ",
									total,
									" 个与岗位直接相关的问题，预计 2 分钟完成。你的回答仅用于本次招聘评估。"
								] }), /* @__PURE__ */ jsx("small", { children: "10:24" })] })]
							}), questions.slice(0, step).map((question, index) => /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsxs("div", {
								className: "message ai",
								children: [/* @__PURE__ */ jsx("span", { children: "AI" }), /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsxs("p", { children: [
									"【",
									question.维度,
									"】",
									question.问题
								] }), /* @__PURE__ */ jsxs("small", { children: ["10:", 25 + index * 2] })] })]
							}), index < step - 1 && /* @__PURE__ */ jsx("div", {
								className: "message human",
								children: /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("p", { children: answers[question.id] || "（已作答）" }), /* @__PURE__ */ jsxs("small", { children: ["10:", 26 + index * 2] })] })
							})] }, question.id))]
						}),
						/* @__PURE__ */ jsx("div", {
							className: "quick-replies",
							children: total === 0 ? /* @__PURE__ */ jsx("button", {
								className: "primary",
								onClick: onSchedule,
								children: "加载中，或暂无问题"
							}) : step < total ? /* @__PURE__ */ jsxs(Fragment$1, { children: [current?.类型 === "单选" ? (current.选项 || []).map((opt) => /* @__PURE__ */ jsx("button", {
								onClick: () => answer(opt),
								children: opt
							}, opt)) : /* @__PURE__ */ jsx("button", {
								onClick: () => answer("是"),
								children: "是"
							}), /* @__PURE__ */ jsx("button", {
								onClick: () => answer("需要说明"),
								children: "需要说明"
							})] }) : /* @__PURE__ */ jsx("button", {
								className: "primary",
								onClick: finish,
								children: "完成初筛并提交"
							})
						})
					]
				}), /* @__PURE__ */ jsxs("aside", {
					className: "panel screening-summary",
					children: [
						/* @__PURE__ */ jsx("p", {
							className: "eyebrow",
							children: "LIVE SUMMARY"
						}),
						/* @__PURE__ */ jsx("h2", { children: "实时结构化摘要" }),
						/* @__PURE__ */ jsxs("div", {
							className: "progress",
							children: [
								/* @__PURE__ */ jsx("span", { children: "初筛进度" }),
								/* @__PURE__ */ jsxs("b", { children: [
									step,
									" / ",
									total
								] }),
								/* @__PURE__ */ jsx("i", { children: /* @__PURE__ */ jsx("em", { style: { width: `${total ? step / total * 100 : 0}%` } }) })
							]
						}),
						/* @__PURE__ */ jsx("dl", { children: questions.map((q, i) => /* @__PURE__ */ jsxs("div", { children: [/* @__PURE__ */ jsx("dt", { children: q.维度 }), /* @__PURE__ */ jsx("dd", {
							className: i < step ? "ok" : "pending",
							children: i < step ? `✓ ${answers[q.id] || "已确认"}` : "待回答"
						})] }, q.id)) }),
						/* @__PURE__ */ jsxs("div", {
							className: "guardrail",
							children: [/* @__PURE__ */ jsx("b", { children: "安全护栏" }), /* @__PURE__ */ jsx("p", { children: "不会询问婚育、民族、健康史等非岗位必要信息。" })]
						}),
						/* @__PURE__ */ jsxs("div", {
							className: "human-note",
							children: [/* @__PURE__ */ jsx("b", { children: "给招聘专员的提示" }), /* @__PURE__ */ jsxs("p", { children: [candidate.gap, "。证书原件需要在面试阶段由人工核验。"] })]
						})
					]
				})]
			})
		]
	});
}
//#endregion
export { Home as default };
