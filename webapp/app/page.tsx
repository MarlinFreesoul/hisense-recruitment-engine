"use client";

import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import { fetchJobs, fetchResults, fetchInterviewQuestions, submitInterview, fetchTalentPool, seedDemo, offerFallback, generateJd, saveJd, screenResume, uploadResume, submitDepartmentDecision, fetchDecisions, departmentPush } from "../lib/api";
import VideoInterview from "../components/VideoInterview";
import type { ApiJob, ApiResult, ApiQuestion, ApiTalentRow } from "../lib/api";

type Job = {
  id: number;
  title: string;
  type: string;
  salary: string;
  location: string;
  experience: string;
  education: string;
  status: "待治理" | "待审核" | "已发布";
  risk: "高" | "中" | "低";
  duplicate?: boolean;
};

type Candidate = {
  id: number;
  name: string;
  initials: string;
  role: string;
  score: number;
  stage: "新简历" | "AI初筛" | "待面试" | "已录用";
  phone: string;
  skills: string[];
  evidence: string[];
  gap: string;
};

// 空占位（数据加载前用，不再用 mock）
const emptyJob: Job = { id: 0, title: "加载中…", type: "", salary: "", location: "", experience: "", education: "", status: "待审核", risk: "低" };
const emptyCandidate: Candidate = { id: 0, name: "加载中…", initials: "?", role: "", score: 0, stage: "AI初筛", phone: "", skills: [], evidence: [], gap: "" };

// 飞书 JD 字段 → 前端 Job 类型
function mapJob(apiJob: ApiJob, index: number): Job {
  return {
    id: index + 1,
    title: apiJob.岗位名称 || "未命名岗位",
    type: apiJob.招聘类型 || "待分类",
    salary: "面议",
    location: apiJob.城市 || "佛山",
    experience: "不限",
    education: "不限",
    status: apiJob.当前状态 === "招聘中" ? "已发布" : "待审核",
    risk: "中",
  };
}

// 飞书评分结果 → 前端 Candidate 类型
function mapCandidate(apiResult: ApiResult, index: number): Candidate {
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
    gap: apiResult.风险等级 ? `风险等级：${apiResult.风险等级}` : "",
  };
}

const navItems = [
  ["dashboard", "运营驾驶舱", "⌁"],
  ["jobs", "岗位治理", "▦"],
  ["candidates", "人才匹配", "◎"],
  ["screening", "上传即打分", "◇"],
  ["evaluation", "人才评价汇总", "▤"],
  ["interview", "视频面试", "▶"],
] as const;

function parseMarkdownJobs(source: string): Job[] {
  const lines = source.split(/\r?\n/).filter((line) => /^\|\s*\d+\s*\|/.test(line));
  return lines.map((line) => {
    const cells = line.split("|").slice(1, -1).map((cell) => cell.trim());
    const title = cells[2] || "未识别岗位";
    const risky = /16\s*[·-]|52\s*岁|男女不限|无犯罪|纹身/.test(title);
    return {
      id: Number(cells[0]), title, type: cells[3] || "待分类", salary: cells[4] || "待确认",
      location: cells[5] || "佛山", experience: cells[6] || "不限", education: cells[7] || "不限",
      status: "待治理", risk: risky || /未识别/.test(title) ? "高" : "中",
      duplicate: /普工|装配|小时工|质检/.test(title),
    };
  });
}

export default function Home() {
  const [active, setActive] = useState<(typeof navItems)[number][0]>("dashboard");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [allJobCount, setAllJobCount] = useState(0);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job>(emptyJob);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate>(emptyCandidate);
  const [query, setQuery] = useState("");
  const [toast, setToast] = useState("");
  const [screenStep, setScreenStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    // 岗位数据：从后端 /jobs 读（飞书 JD 表）
    fetchJobs().then((apiJobs) => {
      const mapped = apiJobs.map(mapJob);
      if (mapped.length) {
        setJobs(mapped);
        setAllJobCount(mapped.length);
        setSelectedJob(mapped[0]);
      }
    }).catch(() => undefined).finally(() => setLoading(false));
    // 候选人数据：从后端 /results 读（飞书评分结果表）
    fetchResults().then((apiResults) => {
      const mapped = apiResults.map(mapCandidate);
      if (mapped.length) {
        setCandidates(mapped);
        setSelectedCandidate(mapped[0]);
      }
    }).catch(() => undefined);
  }, []);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2400);
  };

  const filteredJobs = useMemo(() => jobs.filter((job) => `${job.title}${job.type}`.toLowerCase().includes(query.toLowerCase())), [jobs, query]);
  const duplicateRate = 0; // 重复岗位率暂由后端统计，先占位

  const approveJob = () => {
    setJobs((current) => current.map((job) => job.id === selectedJob.id ? { ...job, status: "已发布", risk: "低" } : job));
    setSelectedJob({ ...selectedJob, status: "已发布", risk: "低" });
    notify("岗位已通过人工复核，并发布到模拟渠道");
  };

  const scheduleInterview = () => {
    setCandidates((current) => current.map((item) => item.id === selectedCandidate.id ? { ...item, stage: "待面试" } : item));
    setSelectedCandidate({ ...selectedCandidate, stage: "待面试" });
    notify("面试已安排：明日 14:30 · 容桂园区");
  };

  const onUploadCandidate = async (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    const r = await uploadResume(f, "", "firstline").catch(() => null);
    setUploading(false);
    if (r && r.success) {
      notify(`已解析并打分：${r.result?.匹配度}分 / ${r.result?.等级}，已入人才池`);
      setActive("evaluation");
    } else {
      notify("解析失败：" + (r?.error || "未知"));
    }
    e.target.value = "";
  };

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">H</span><div><b>Hisense HireAI</b><small>招聘运营智能体</small></div></div>
        <div className="pilot-badge"><i /> 黑客松演示环境</div>
        <nav aria-label="主导航">
          {navItems.map(([id, label, icon]) => <button key={id} className={active === id ? "active" : ""} onClick={() => setActive(id)}><span>{icon}</span>{label}{id === "jobs" && jobs.length > 0 && <em>{jobs.length}</em>}</button>)}
        </nav>
        <div className="side-insight"><span>本周 AI 提效</span><strong>26.4h</strong><small>预计节省招聘工时</small><div><i style={{ width: "78%" }} /></div></div>
        <div className="profile"><span>HR</span><div><b>招聘运营中心</b><small>企业管理员</small></div><button aria-label="更多选项">•••</button></div>
      </aside>

      <section className="workspace">
        <header className="topbar"><div><span className="crumb">海信容声广州公司 /</span><b>{navItems.find((item) => item[0] === active)?.[1]}</b></div><div className="top-actions"><button className="icon-btn" aria-label="通知">♢<i /></button><button className="primary" onClick={() => { setActive("jobs"); notify("已打开岗位导入工作台"); }}>＋ 导入岗位数据</button></div></header>

        {active === "dashboard" && <Dashboard allJobCount={allJobCount} duplicateRate={duplicateRate} candidates={candidates} onNavigate={setActive} />}

        {active === "jobs" && <section className="page jobs-page">
          <div className="page-heading"><div><p className="eyebrow">JOB GOVERNANCE</p><h1>岗位治理中心</h1><p>AI 已完成首轮清洗，已从飞书同步岗位数据，等待人工复核与治理。</p></div><button className="outline" onClick={() => notify("已生成岗位异常清单 CSV")}>导出治理报告</button></div>
          <div className="split-layout">
            <div className="panel job-list"><div className="panel-tools"><label>⌕<input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索岗位或类型" /></label><button>全部岗位⌄</button></div><div className="list-head"><span>岗位 / 工种</span><span>薪资</span><span>风险</span></div>{filteredJobs.map((job) => <button className={`job-row ${selectedJob.id === job.id ? "selected" : ""}`} key={job.id} onClick={() => setSelectedJob(job)}><div><b>{job.title}</b><small>{job.type} · {job.location}</small></div><span>{job.salary}</span><span className={`risk risk-${job.risk}`}>{job.risk}</span></button>)}</div>
            <JobWorkbench job={selectedJob} onApprove={approveJob} onNotify={notify} />
          </div>
        </section>}

        {active === "candidates" && <section className="page candidates-page">
          <div className="page-heading"><div><p className="eyebrow">TALENT MATCHING</p><h1>人才匹配工作台</h1><p>规则校验＋语义匹配＋人工终审，每个结论都有可追溯证据。</p></div><label className="primary" style={{ cursor: "pointer" }}>{uploading ? "解析中…" : "＋ 上传简历（投递即筛选）"}<input type="file" accept=".pdf,.txt,.md,.docx" style={{ display: "none" }} onChange={onUploadCandidate} /></label></div>
          <div className="candidate-grid">{candidates.map((candidate) => <button key={candidate.id} className={`candidate-card ${selectedCandidate.id === candidate.id ? "selected" : ""}`} onClick={() => setSelectedCandidate(candidate)}><div className="candidate-top"><span className="avatar">{candidate.initials}</span><div><b>{candidate.name}</b><small>{candidate.phone}</small></div><strong>{candidate.score}<small>匹配分</small></strong></div><h3>{candidate.role}</h3><div className="skill-row">{candidate.skills.map((skill) => <span key={skill}>{skill}</span>)}</div><div className="card-foot"><span className={`stage stage-${candidate.stage}`}>{candidate.stage}</span><span>查看证据 →</span></div></button>)}</div>
          <CandidateEvidence candidate={selectedCandidate} onSchedule={scheduleInterview} />
        </section>}

        {active === "screening" && <><ResumeUpload /><Screening candidate={selectedCandidate} step={screenStep} setStep={setScreenStep} onSchedule={scheduleInterview} /></>}
        {active === "interview" && <VideoInterview />}
      </section>

      {active === "evaluation" && <Evaluation notify={notify} />}
      {toast && <div className="toast"><span>✓</span>{toast}</div>}
    </main>
  );
}

function Dashboard({ allJobCount, duplicateRate, candidates, onNavigate }: { allJobCount: number; duplicateRate: number; candidates: Candidate[]; onNavigate: (id: "jobs" | "candidates" | "screening") => void }) {
  return <section className="page dashboard">
    <div className="hero-row"><div><p className="eyebrow">GOOD MORNING, RECRUITING TEAM</p><h1>招聘全局，一屏掌握。</h1><p>AI 正在监控岗位质量与候选人转化，今天有 <b>7 项关键任务</b>需要处理。</p></div><div className="ai-status"><span className="orb">✦</span><div><b>4 个智能体运行正常</b><small>刚刚完成 16 次分析 · 0 项异常</small></div><i /></div></div>
    <div className="metric-grid">
      <article><span>有效岗位</span><strong>{allJobCount}<small>条</small></strong><em className="up">↑ 12 本周新增</em><i className="metric-icon blue">▦</i></article>
      <article><span>待处理候选人</span><strong>{candidates.length}<small>人</small></strong><em>其中 {candidates.filter((c) => c.score >= 80).length} 人高匹配</em><i className="metric-icon purple">◎</i></article>
      <article><span>重复岗位率</span><strong>{duplicateRate}<small>%</small></strong><em className="down">↓ 治理后预计 18%</em><i className="metric-icon amber">⚠</i></article>
      <article><span>平均招聘周期</span><strong>6.8<small>天</small></strong><em className="up">↓ 2.4 天 AI 提效</em><i className="metric-icon green">◷</i></article>
    </div>
    <div className="dashboard-grid">
      <article className="panel funnel"><div className="panel-title"><div><p className="eyebrow">RECRUITMENT FUNNEL</p><h2>招聘转化漏斗</h2></div><span>过去 30 天⌄</span></div><div className="funnel-chart"><div style={{ width: "100%" }}><span>简历进入</span><b>326</b><small>100%</small></div><div style={{ width: "82%" }}><span>AI 初筛</span><b>218</b><small>66.9%</small></div><div style={{ width: "61%" }}><span>人工复核</span><b>128</b><small>39.3%</small></div><div style={{ width: "43%" }}><span>安排面试</span><b>74</b><small>22.7%</small></div><div style={{ width: "25%" }}><span>确认录用</span><b>31</b><small>9.5%</small></div></div></article>
      <article className="panel actions"><div className="panel-title"><div><p className="eyebrow">ACTION CENTER</p><h2>今日行动中心</h2></div><button onClick={() => onNavigate("jobs")}>查看全部 →</button></div>
        <button onClick={() => onNavigate("jobs")}><span className="action-icon red">!</span><div><b>23 项岗位风险待复核</b><small>含年龄限制、薪资冲突与标题残缺</small></div><em>高优先级</em></button>
        <button onClick={() => onNavigate("candidates")}><span className="action-icon purple">◎</span><div><b>15 位高匹配候选人</b><small>建议今日完成首次联系</small></div><em>人才匹配</em></button>
        <button onClick={() => onNavigate("screening")}><span className="action-icon blue">◇</span><div><b>8 场 AI 初筛已完成</b><small>摘要与证据等待人工终审</small></div><em>待审核</em></button>
      </article>
      <article className="panel agent-feed"><div className="panel-title"><div><p className="eyebrow">AGENT ACTIVITY</p><h2>智能体实时动态</h2></div><span className="live"><i /> LIVE</span></div><div className="feed-item"><span>治</span><div><b>岗位治理智能体</b><p>合并 17 条“容桂装配工”重复信息，发现 3 项薪资冲突。</p><small>2 分钟前</small></div></div><div className="feed-item"><span>配</span><div><b>人才匹配智能体</b><p>完成陈浩与“设备维修工程师”的证据化匹配，得分 92。</p><small>6 分钟前</small></div></div><div className="feed-item"><span>筛</span><div><b>AI 初筛智能体</b><p>李敏已完成 5 个必要问题，夜班意愿需人工确认。</p><small>11 分钟前</small></div></div></article>
      <article className="panel efficiency"><div className="panel-title"><div><p className="eyebrow">EFFICIENCY</p><h2>AI 提效价值</h2></div><span>本周</span></div><div className="efficiency-ring"><div><strong>26.4</strong><small>节省工时</small></div></div><div className="efficiency-list"><p><span>岗位整理</span><b>11.2h</b></p><p><span>简历初筛</span><b>9.6h</b></p><p><span>沟通与报告</span><b>5.6h</b></p></div></article>
    </div>
  </section>;
}

function JobWorkbench({ job, onApprove, onNotify }: { job: Job; onApprove: () => void; onNotify: (m: string) => void }) {
  const [jdOpen, setJdOpen] = useState(false);
  return <article className="panel job-workbench"><div className="workbench-head"><div><span className={`risk risk-${job.risk}`}>{job.risk}风险</span><h2>{job.title}</h2><p>编号 HS-GZ-{String(job.id).padStart(3, "0")} · {job.status}</p></div><button aria-label="更多">•••</button></div><div className="compare-label"><span>原始 OCR 文案</span><span>AI 标准化岗位画像</span></div><div className="compare"><div className="raw-copy"><p>{job.title} 佛山 {job.experience} 职位描述：包吃住 / 工资 {job.salary} / 立即沟通，工作简单易上手，具体以现场安排为准。</p><span>来源：BOSS 公开页面截图 OCR</span></div><div className="clean-copy"><h3>{job.title}</h3><dl><div><dt>岗位类别</dt><dd>{job.type}</dd></div><div><dt>工作地点</dt><dd>{job.location} · 容桂园区</dd></div><div><dt>薪资范围</dt><dd>{job.salary}</dd></div><div><dt>经验 / 学历</dt><dd>{job.experience} / {job.education}</dd></div><div><dt>用工性质</dt><dd>{job.type.includes("临时") ? "临时用工" : "正式用工"}</dd></div><div><dt>班次</dt><dd>两班倒 · 月休 4 天</dd></div></dl></div></div><div className="risk-box"><div><span>⚠</span><div><b>AI 合规与质量检查</b><p>发现原文职责不完整、薪资口径需确认；涉及年龄或个人条件时不得作为 AI 自动淘汰依据。</p></div></div><em>需人工复核</em></div><div className="rationale"><b>本次优化依据</b><span>统一岗位命名</span><span>结构化薪资</span><span>补全班次信息</span><span>移除歧视性表达</span></div><div className="workbench-actions"><button className="outline" onClick={() => setJdOpen(true)}>✎ 生成 / 编辑 JD</button><button className="primary" onClick={onApprove}>✓ 人工确认并发布</button></div>{jdOpen && <JdEditor jobTitle={job.title} onClose={() => setJdOpen(false)} onSaved={(m) => onNotify(m)} />}</article>;
}

function CandidateEvidence({ candidate, onSchedule }: { candidate: Candidate; onSchedule: () => void }) {
  return <article className="panel evidence-panel"><div className="evidence-score"><div className="score-ring"><span>{candidate.score}</span><small>/ 100</small></div><div><p className="eyebrow">EXPLAINABLE MATCH</p><h2>{candidate.name} × {candidate.role}</h2><p>综合硬条件、经历相关度与到岗可行性；最终决定需人工确认。</p></div><button className="primary" onClick={onSchedule}>安排面试</button></div><div className="evidence-grid"><div><h3>匹配证据</h3>{candidate.evidence.map((item) => <p key={item}><span>✓</span>{item}</p>)}</div><div><h3>待确认缺口</h3><p className="gap"><span>!</span>{candidate.gap}</p><p className="gap"><span>!</span>请核验证书原件与有效期</p></div><div><h3>评分构成</h3><p><span>硬条件</span><b>36 / 40</b></p><p><span>技能经历</span><b>32 / 35</b></p><p><span>到岗适配</span><b>24 / 25</b></p></div></div></article>;
}

const FAMILY_OPTIONS: [string, string][] = [
  ["firstline", "一线生产"],
  ["process-equipment", "工艺 / 设备"],
  ["quality", "质量 / 检验"],
  ["procurement-logistics", "采购 / 物流"],
  ["production-management", "现场管理"],
];

function ResumeUpload() {
  const [text, setText] = useState("");
  const [jobName, setJobName] = useState("装配包装工");
  const [family, setFamily] = useState("firstline");
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const samples: Record<string, string> = {
    firstline: "姓名：刘芳。大专，电子专业，3年装配经验，有电工证，接受倒班，一个月内到岗。",
    "process-equipment": "姓名：陈浩。本科，机械制造专业，5 年设备维修经验，持有电工证、钳工证，接受倒班，随时到岗。",
  };
  const run = async () => {
    if (!text.trim()) return;
    setBusy(true);
    const r = await screenResume(text, jobName, family).catch(() => null);
    setRes(r);
    setBusy(false);
  };
  const onFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true);
    const r = await uploadResume(f, jobName, family).catch(() => null);
    setRes(r);
    setBusy(false);
    e.target.value = "";
  };
  return (
    <section className="panel" style={{ marginBottom: 18, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div><p className="eyebrow">RESUME UPLOAD</p><h2 style={{ margin: 0 }}>上传即打分</h2></div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="outline" onClick={() => setText(samples.firstline)}>示例·一线</button>
          <button className="outline" onClick={() => setText(samples["process-equipment"])}>示例·设备</button>
        </div>
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="粘贴简历文本…" rows={4} style={{ width: "100%", border: "1px solid var(--line)", borderRadius: 10, padding: 12, resize: "vertical" }} />
      <div style={{ display: "flex", gap: 10, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
        <input value={jobName} onChange={(e) => setJobName(e.target.value)} placeholder="岗位名" style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "8px 10px" }} />
        <select value={family} onChange={(e) => setFamily(e.target.value)} style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "8px 10px" }}>
          {FAMILY_OPTIONS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <label className="outline" style={{ cursor: "pointer" }}>{busy ? "解析中…" : "📎 上传简历文件"}<input type="file" accept=".pdf,.txt,.md,.docx" style={{ display: "none" }} onChange={onFile} /></label>
        <button className="primary" disabled={busy} onClick={run}>{busy ? "打分中…" : "开始打分"}</button>
      </div>
      {res && res.success && (
        <div style={{ marginTop: 14, background: "#f7faff", border: "1px solid #dbe7ff", borderRadius: 10, padding: 14 }}>
          <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
            <div><b style={{ fontSize: 22 }}>{res.result?.匹配度}</b><small> / 100 匹配度</small></div>
            <div>等级：<b>{res.result?.等级}</b></div>
            <div>风险：<b>{res.result?.风险等级}</b></div>
            <div>入池：{res.talent_pool?.pooled ? "已入人才池 " + res.talent_pool?.candidate_id : "未入池"}</div>
          </div>
          <p style={{ margin: "10px 0 0", color: "var(--muted)" }}>匹配总结：{res.result?.匹配总结}</p>
        </div>
      )}
      {res && !res.success && <p style={{ color: "var(--red)", marginTop: 10 }}>{res.error}</p>}
    </section>
  );
}

function Evaluation({ notify }: { notify: (m: string) => void }) {
  const [rows, setRows] = useState<ApiTalentRow[]>([]);
  const [fallback, setFallback] = useState<any>(null);
  const [decisions, setDecisions] = useState<Array<Record<string, unknown>>>([]);
  const [reviewFor, setReviewFor] = useState<string | null>(null);
  const [reviewDecision, setReviewDecision] = useState("通过");
  const [reviewNote, setReviewNote] = useState("");

  const load = async () => {
    try { setRows(await fetchTalentPool()); } catch {}
    try { setDecisions(await fetchDecisions()); } catch {}
  };
  useEffect(() => { load(); }, []);

  const onSeed = async () => {
    await seedDemo().catch(() => undefined);
    notify("已载入 6 份演示候选人");
    load();
  };
  const onFallback = async (row: ApiTalentRow) => {
    const r = await offerFallback(row.jobFamily, row.candidateId).catch(() => null);
    if (r && r.success) { setFallback(r); notify("已触发 Offer 递补"); load(); }
  };
  const onPush = async (row: ApiTalentRow) => {
    const r = await departmentPush({ candidate_id: row.candidateId, name: row.name, job_family: row.jobFamily }).catch(() => null);
    if (r && r.success) { notify("已推送用人部门复核"); load(); }
    else if (r) notify("推送失败：" + (r.error || "未知"));
  };
  const onReview = async (row: ApiTalentRow) => {
    const r = await submitDepartmentDecision({
      candidate_id: row.candidateId, name: row.name, job_family: row.jobFamily,
      decision: reviewDecision, note: reviewNote,
    }).catch(() => null);
    if (r && r.success) { notify(r.message || "已记录复核"); setReviewFor(null); setReviewNote(""); load(); }
  };

  return (
    <section className="page evaluation-page">
      <div className="page-heading"><div><p className="eyebrow">TALENT EVALUATION</p><h1>人才评价汇总</h1><p>合格候选人自动入库、分类标签、横向对比；选定者放弃 Offer 时按匹配度秒级递补下一顺位。</p></div><button className="primary" onClick={onSeed}>⟳ 载入演示数据</button></div>

      {fallback && (
        <div style={{ background: "#eafaf2", border: "1px solid #b7e6cf", borderRadius: 12, padding: 14, marginBottom: 14 }}>
          <b>Offer 递补结果</b>
          <p style={{ margin: "6px 0" }}>{fallback.fallback_reason}</p>
          {fallback.next_best && <span style={{ color: "var(--green)" }}>→ 推进：{fallback.next_best.name}（{fallback.next_best.totalScore}分 / {fallback.next_best.grade}）</span>}
        </div>
      )}

      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead><tr style={{ background: "#f4f6fa", textAlign: "left" }}>
            <th style={th}>候选人</th><th style={th}>岗位</th><th style={th}>匹配度</th><th style={th}>等级</th><th style={th}>风险</th><th style={th}>标签</th><th style={th}>状态</th><th style={th}>操作</th>
          </tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.candidateId} style={{ borderTop: "1px solid var(--line)" }}>
                <td style={td}><b>{row.name}</b></td>
                <td style={td}>{row.jobName}</td>
                <td style={td}><b>{row.totalScore}</b></td>
                <td style={td}>{row.grade}</td>
                <td style={td}><span className={`risk risk-${row.riskLevel}`}>{row.riskLevel}</span></td>
                <td style={td}>{(row.tags || []).join("、")}</td>
                <td style={td}>{row.status}</td>
                <td style={td}>
                  <button className="outline" style={{ marginRight: 6, padding: "4px 8px" }} onClick={() => onPush(row)}>推送给用人部门</button>
                  <button className="outline" style={{ marginRight: 6, padding: "4px 8px" }} onClick={() => onFallback(row)}>放弃Offer递补</button>
                  <button className="outline" style={{ padding: "4px 8px" }} onClick={() => setReviewFor(row.candidateId)}>部门复核</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p style={{ padding: 18, color: "var(--muted)" }}>暂无数据，点击右上角「载入演示数据」。</p>}
      </div>

      {reviewFor && (
        <div className="panel" style={{ marginTop: 14, padding: 16 }}>
          <h3 style={{ marginTop: 0 }}>用人部门复核</h3>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <select value={reviewDecision} onChange={(e) => setReviewDecision(e.target.value)} style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "8px 10px" }}>
              <option value="通过">通过</option><option value="不通过">不通过</option>
            </select>
            <input value={reviewNote} onChange={(e) => setReviewNote(e.target.value)} placeholder="备注（选填）" style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "8px 10px", minWidth: 220 }} />
            <button className="primary" onClick={() => { const r = rows.find((x) => x.candidateId === reviewFor); if (r) onReview(r); }}>提交并推送 HR</button>
            <button className="outline" onClick={() => setReviewFor(null)}>取消</button>
          </div>
        </div>
      )}

      <div className="panel" style={{ marginTop: 14, padding: 16 }}>
        <h3 style={{ marginTop: 0 }}>用人部门复核记录（{decisions.length}）</h3>
        {decisions.map((d, i) => (
          <div key={i} style={{ display: "flex", gap: 10, padding: "8px 0", borderTop: i ? "1px solid var(--line)" : "none", fontSize: 13 }}>
            <b>{String(d.name)}</b><span style={{ color: d.decision === "通过" ? "var(--green)" : "var(--red)" }}>{String(d.decision)}</span>
            <span style={{ color: "var(--muted)" }}>{String(d.note || "无备注")}</span>
            <small style={{ marginLeft: "auto", color: "var(--muted)" }}>{String(d.at)}</small>
          </div>
        ))}
        {!decisions.length && <p style={{ color: "var(--muted)" }}>暂无复核记录。</p>}
      </div>
    </section>
  );
}

function JdEditor({ jobTitle, onClose, onSaved }: { jobTitle: string; onClose: () => void; onSaved: (m: string) => void }) {
  const [family, setFamily] = useState("firstline");
  const [position, setPosition] = useState(jobTitle || "装配包装工");
  const [location, setLocation] = useState("佛山顺德");
  const [salary, setSalary] = useState("5000-6000元/月");
  const [extraHard, setExtraHard] = useState("");
  const [extraSkills, setExtraSkills] = useState("");
  const [jd, setJd] = useState<any>(null);
  const [saved, setSaved] = useState(false);

  const buildParams = () => {
    const p: Record<string, unknown> = { position, location, salary };
    if (extraHard) p.extra_hard = extraHard.split(/[，,、]/).map((s) => s.trim()).filter(Boolean);
    if (extraSkills) p.extra_skills = extraSkills.split(/[，,、]/).map((s) => s.trim()).filter(Boolean);
    return p;
  };
  const gen = async () => { const r = await generateJd(family, buildParams()).catch(() => null); if (r && r.success) setJd(r.jd); };
  const save = async () => {
    const r = await saveJd(family, buildParams()).catch(() => null);
    if (r && r.success) { setSaved(true); onSaved("JD 已保存并写回飞书招聘需求表"); }
    else if (r) onSaved("JD 保存失败：" + (r.error || "未知"));
  };

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(8,16,29,.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 16 }}>
      <div onClick={(e) => e.stopPropagation()} className="panel" style={{ maxWidth: 560, width: "100%", maxHeight: "90vh", overflow: "auto", padding: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><h2 style={{ margin: 0 }}>生成 / 编辑 JD</h2><button className="outline" onClick={onClose}>关闭</button></div>
        <div style={{ display: "grid", gap: 10, marginTop: 14 }}>
          <label style={lbl}>岗位族
            <select value={family} onChange={(e) => setFamily(e.target.value)} style={inp}>
              <option value="firstline">一线生产</option><option value="process-equipment">工艺 / 设备</option><option value="quality">质量 / 检验</option><option value="procurement-logistics">采购 / 物流</option><option value="production-management">现场管理</option>
            </select>
          </label>
          <label style={lbl}>岗位名称<input value={position} onChange={(e) => setPosition(e.target.value)} style={inp} /></label>
          <label style={lbl}>工作地点<input value={location} onChange={(e) => setLocation(e.target.value)} style={inp} /></label>
          <label style={lbl}>薪资<input value={salary} onChange={(e) => setSalary(e.target.value)} style={inp} /></label>
          <label style={lbl}>补充硬条件（逗号分隔）<input value={extraHard} onChange={(e) => setExtraHard(e.target.value)} style={inp} placeholder="如：需高处作业证" /></label>
          <label style={lbl}>补充技能（逗号分隔）<input value={extraSkills} onChange={(e) => setExtraSkills(e.target.value)} style={inp} placeholder="如：PLC、焊接" /></label>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
          <button className="primary" onClick={gen}>生成 JD</button>
          <button className="outline" onClick={save}>保存（写回飞书）</button>
          {saved && <span style={{ color: "var(--green)", alignSelf: "center" }}>已保存 ✓</span>}
        </div>
        {jd && (
          <pre style={{ background: "#0e182a", color: "#cfe3ff", borderRadius: 10, padding: 14, marginTop: 14, fontSize: 12, overflow: "auto" }}>{JSON.stringify(jd, null, 2)}</pre>
        )}
      </div>
    </div>
  );
}

const th = { padding: "10px 12px", fontWeight: 600, color: "var(--muted)" };
const td = { padding: "10px 12px" };
const lbl = { display: "grid", gap: 4, fontSize: 12, color: "var(--muted)" };
const inp = { border: "1px solid var(--line)", borderRadius: 8, padding: "8px 10px", fontSize: 14, color: "var(--ink)" };

function Screening({ candidate, step, setStep, onSchedule }: { candidate: Candidate; step: number; setStep: (n: number) => void; onSchedule: () => void }) {
  const [questions, setQuestions] = useState<ApiQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [assessment, setAssessment] = useState("");

  useEffect(() => {
    setStep(0);
    setAnswers({});
    fetchInterviewQuestions(candidate.name, assessment).then((d) => {
      if (d.questions?.length) setQuestions(d.questions);
    }).catch(() => undefined);
  }, [candidate.name, assessment]);

  const total = questions.length || 0;
  const current = questions[step - 1];

  const answer = (value: string) => {
    if (current) setAnswers((cur) => ({ ...cur, [current.id]: value }));
    setStep(step + 1);
  };

  const finish = async () => {
    await submitInterview(candidate.name, candidate.role, answers).catch(() => undefined);
    onSchedule();
  };

  return <section className="page screening-page"><div className="page-heading"><div><p className="eyebrow">AI SCREENING</p><h1>结构化 AI 初筛</h1><p>只询问岗位必要信息，敏感问题自动拦截，所有结论等待人工终审。</p></div><span className="privacy-chip">盾 隐私脱敏已开启</span></div>
    <div style={{ marginBottom: 14 }}>
      <label style={lbl}>候选人测评报告（可选，粘贴后系统据此生成个性化追问）
        <textarea value={assessment} onChange={(e) => setAssessment(e.target.value)} placeholder="如：逻辑思维 75 分（待提升）；团队协作 88 分" style={{ ...inp, minHeight: 56, resize: "vertical" }} />
      </label>
    </div>
    <div className="screen-layout"><article className="panel conversation"><div className="conversation-head"><span className="avatar">{candidate.initials}</span><div><b>{candidate.name}</b><small>{candidate.role} · 匹配分 {candidate.score}</small></div><span className="live"><i /> AI 初筛中</span></div><div className="messages"><div className="message ai"><span>AI</span><div><p>你好，{candidate.name.slice(0, 1)}先生。接下来有 {total} 个与岗位直接相关的问题，预计 2 分钟完成。你的回答仅用于本次招聘评估。</p><small>10:24</small></div></div>{questions.slice(0, step).map((question, index) => <div key={question.id}><div className="message ai"><span>AI</span><div><p>【{question.维度}】{question.问题}</p><small>10:{25 + index * 2}</small></div></div>{index < step - 1 && <div className="message human"><div><p>{answers[question.id] || "（已作答）"}</p><small>10:{26 + index * 2}</small></div></div>}</div>)}</div><div className="quick-replies">{total === 0 ? <button className="primary" onClick={onSchedule}>加载中，或暂无问题</button> : step < total ? <>{current?.类型 === "单选" ? (current.选项 || []).map((opt) => <button key={opt} onClick={() => answer(opt)}>{opt}</button>) : <button onClick={() => answer("是")}>是</button>}<button onClick={() => answer("需要说明")}>需要说明</button></> : <button className="primary" onClick={finish}>完成初筛并提交</button>}</div></article><aside className="panel screening-summary"><p className="eyebrow">LIVE SUMMARY</p><h2>实时结构化摘要</h2><div className="progress"><span>初筛进度</span><b>{step} / {total}</b><i><em style={{ width: `${total ? step / total * 100 : 0}%` }} /></i></div><dl>{questions.map((q, i) => <div key={q.id}><dt>{q.维度}</dt><dd className={i < step ? "ok" : "pending"}>{i < step ? `✓ ${answers[q.id] || "已确认"}` : "待回答"}</dd></div>)}</dl><div className="guardrail"><b>安全护栏</b><p>不会询问婚育、民族、健康史等非岗位必要信息。</p></div><div className="human-note"><b>给招聘专员的提示</b><p>{candidate.gap}。证书原件需要在面试阶段由人工核验。</p></div></aside></div></section>;
}
