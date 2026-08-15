"use client";

import { useEffect, useMemo, useState } from "react";

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

const seedJobs: Job[] = [
  { id: 1, title: "精益物流工程师", type: "物流/精益", salary: "12-20K·13薪", location: "佛山", experience: "3-5年", education: "本科", status: "已发布", risk: "低" },
  { id: 16, title: "整机性能测试员", type: "质量/测试", salary: "5-6K", location: "佛山", experience: "1-3年", education: "大专", status: "待审核", risk: "中" },
  { id: 39, title: "嵌入式高级软件开发工程师", type: "研发技术", salary: "18-55K", location: "佛山", experience: "5-10年", education: "本科", status: "待审核", risk: "中" },
  { id: 56, title: "设备维修电工", type: "设备/维修", salary: "6-8K", location: "佛山", experience: "1-3年", education: "不限", status: "已发布", risk: "低" },
  { id: 72, title: "设备维修工程师", type: "设备/维修", salary: "12-18K", location: "佛山", experience: "3-5年", education: "不限", status: "待治理", risk: "中" },
  { id: 73, title: "容桂冰箱装配工", type: "一线生产", salary: "5-6K", location: "佛山", experience: "不限", education: "不限", status: "待审核", risk: "高", duplicate: true },
  { id: 79, title: "现场质量检验员", type: "质量/测试", salary: "5-6K", location: "佛山", experience: "不限", education: "不限", status: "已发布", risk: "低", duplicate: true },
  { id: 98, title: "钣金工", type: "一线生产", salary: "6-7K", location: "佛山", experience: "不限", education: "不限", status: "待治理", risk: "低", duplicate: true },
];

const seedCandidates: Candidate[] = [
  { id: 1, name: "陈浩", initials: "CH", role: "设备维修工程师", score: 92, stage: "待面试", phone: "138****2041", skills: ["低压电工证", "设备维保", "PLC"], evidence: ["4年家电制造设备维保经验", "持有效低压电工证", "可接受倒班，7天内到岗"], gap: "未确认高空作业经验" },
  { id: 2, name: "李敏", initials: "LM", role: "现场质量检验员", score: 86, stage: "AI初筛", phone: "156****8830", skills: ["来料检验", "QC七工具", "Excel"], evidence: ["2年制造业质检经验", "熟悉抽样检验流程", "居住地距厂区8公里"], gap: "需确认夜班意愿" },
  { id: 3, name: "周凯", initials: "ZK", role: "嵌入式高级软件开发工程师", score: 78, stage: "新简历", phone: "189****1176", skills: ["C/C++", "FreeRTOS", "STM32"], evidence: ["5年嵌入式开发经验", "量产项目经历", "本科电子信息专业"], gap: "家电行业经验不足" },
  { id: 4, name: "王强", initials: "WQ", role: "容桂冰箱装配工", score: 73, stage: "AI初筛", phone: "133****6092", skills: ["装配", "包装", "两班倒"], evidence: ["1年流水线装配经验", "可立即到岗", "接受宿舍安排"], gap: "身份材料待补充" },
];

const navItems = [
  ["dashboard", "运营驾驶舱", "⌁"],
  ["jobs", "岗位治理", "▦"],
  ["candidates", "人才匹配", "◎"],
  ["screening", "AI 初筛", "◇"],
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
  const [jobs, setJobs] = useState<Job[]>(seedJobs);
  const [allJobCount, setAllJobCount] = useState(115);
  const [candidates, setCandidates] = useState(seedCandidates);
  const [selectedJob, setSelectedJob] = useState<Job>(seedJobs[5]);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate>(seedCandidates[0]);
  const [query, setQuery] = useState("");
  const [toast, setToast] = useState("");
  const [screenStep, setScreenStep] = useState(1);

  useEffect(() => {
    fetch("/data/hisense_boss_jobs_structured.md").then((r) => r.text()).then((text) => {
      const parsed = parseMarkdownJobs(text);
      if (parsed.length) setAllJobCount(parsed.length);
    }).catch(() => undefined);
  }, []);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2400);
  };

  const filteredJobs = useMemo(() => jobs.filter((job) => `${job.title}${job.type}`.toLowerCase().includes(query.toLowerCase())), [jobs, query]);
  const duplicateRate = Math.round((82 / allJobCount) * 100);

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

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">H</span><div><b>Hisense HireAI</b><small>招聘运营智能体</small></div></div>
        <div className="pilot-badge"><i /> 黑客松演示环境</div>
        <nav aria-label="主导航">
          {navItems.map(([id, label, icon]) => <button key={id} className={active === id ? "active" : ""} onClick={() => setActive(id)}><span>{icon}</span>{label}{id === "jobs" && <em>23</em>}</button>)}
        </nav>
        <div className="side-insight"><span>本周 AI 提效</span><strong>26.4h</strong><small>预计节省招聘工时</small><div><i style={{ width: "78%" }} /></div></div>
        <div className="profile"><span>HR</span><div><b>招聘运营中心</b><small>企业管理员</small></div><button aria-label="更多选项">•••</button></div>
      </aside>

      <section className="workspace">
        <header className="topbar"><div><span className="crumb">海信容声广州公司 /</span><b>{navItems.find((item) => item[0] === active)?.[1]}</b></div><div className="top-actions"><button className="icon-btn" aria-label="通知">♢<i /></button><button className="primary" onClick={() => { setActive("jobs"); notify("已打开岗位导入工作台"); }}>＋ 导入岗位数据</button></div></header>

        {active === "dashboard" && <Dashboard allJobCount={allJobCount} duplicateRate={duplicateRate} onNavigate={setActive} />}

        {active === "jobs" && <section className="page jobs-page">
          <div className="page-heading"><div><p className="eyebrow">JOB GOVERNANCE</p><h1>岗位治理中心</h1><p>AI 已完成首轮清洗，发现 <b>82 个疑似重复岗位</b> 与 <b>23 项待人工复核</b>。</p></div><button className="outline" onClick={() => notify("已生成岗位异常清单 CSV")}>导出治理报告</button></div>
          <div className="split-layout">
            <div className="panel job-list"><div className="panel-tools"><label>⌕<input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索岗位或类型" /></label><button>全部岗位⌄</button></div><div className="list-head"><span>岗位 / 工种</span><span>薪资</span><span>风险</span></div>{filteredJobs.map((job) => <button className={`job-row ${selectedJob.id === job.id ? "selected" : ""}`} key={job.id} onClick={() => setSelectedJob(job)}><div><b>{job.title}</b><small>{job.type} · {job.location}</small></div><span>{job.salary}</span><span className={`risk risk-${job.risk}`}>{job.risk}</span></button>)}</div>
            <JobWorkbench job={selectedJob} onApprove={approveJob} onNotify={notify} />
          </div>
        </section>}

        {active === "candidates" && <section className="page candidates-page">
          <div className="page-heading"><div><p className="eyebrow">TALENT MATCHING</p><h1>人才匹配工作台</h1><p>规则校验＋语义匹配＋人工终审，每个结论都有可追溯证据。</p></div><button className="primary" onClick={() => notify("请拖入 PDF、Word 或 Excel 简历")}>＋ 添加候选人</button></div>
          <div className="candidate-grid">{candidates.map((candidate) => <button key={candidate.id} className={`candidate-card ${selectedCandidate.id === candidate.id ? "selected" : ""}`} onClick={() => setSelectedCandidate(candidate)}><div className="candidate-top"><span className="avatar">{candidate.initials}</span><div><b>{candidate.name}</b><small>{candidate.phone}</small></div><strong>{candidate.score}<small>匹配分</small></strong></div><h3>{candidate.role}</h3><div className="skill-row">{candidate.skills.map((skill) => <span key={skill}>{skill}</span>)}</div><div className="card-foot"><span className={`stage stage-${candidate.stage}`}>{candidate.stage}</span><span>查看证据 →</span></div></button>)}</div>
          <CandidateEvidence candidate={selectedCandidate} onSchedule={scheduleInterview} />
        </section>}

        {active === "screening" && <Screening candidate={selectedCandidate} step={screenStep} setStep={setScreenStep} onSchedule={scheduleInterview} />}
      </section>
      {toast && <div className="toast"><span>✓</span>{toast}</div>}
    </main>
  );
}

function Dashboard({ allJobCount, duplicateRate, onNavigate }: { allJobCount: number; duplicateRate: number; onNavigate: (id: "jobs" | "candidates" | "screening") => void }) {
  return <section className="page dashboard">
    <div className="hero-row"><div><p className="eyebrow">GOOD MORNING, RECRUITING TEAM</p><h1>招聘全局，一屏掌握。</h1><p>AI 正在监控岗位质量与候选人转化，今天有 <b>7 项关键任务</b>需要处理。</p></div><div className="ai-status"><span className="orb">✦</span><div><b>4 个智能体运行正常</b><small>刚刚完成 16 次分析 · 0 项异常</small></div><i /></div></div>
    <div className="metric-grid">
      <article><span>有效岗位</span><strong>{allJobCount}<small>条</small></strong><em className="up">↑ 12 本周新增</em><i className="metric-icon blue">▦</i></article>
      <article><span>待处理候选人</span><strong>47<small>人</small></strong><em>其中 15 人高匹配</em><i className="metric-icon purple">◎</i></article>
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
  return <article className="panel job-workbench"><div className="workbench-head"><div><span className={`risk risk-${job.risk}`}>{job.risk}风险</span><h2>{job.title}</h2><p>编号 HS-GZ-{String(job.id).padStart(3, "0")} · {job.status}</p></div><button aria-label="更多">•••</button></div><div className="compare-label"><span>原始 OCR 文案</span><span>AI 标准化岗位画像</span></div><div className="compare"><div className="raw-copy"><p>{job.title} 佛山 {job.experience} 职位描述：包吃住 / 工资 {job.salary} / 立即沟通，工作简单易上手，具体以现场安排为准。</p><span>来源：BOSS 公开页面截图 OCR</span></div><div className="clean-copy"><h3>{job.title}</h3><dl><div><dt>岗位类别</dt><dd>{job.type}</dd></div><div><dt>工作地点</dt><dd>{job.location} · 容桂园区</dd></div><div><dt>薪资范围</dt><dd>{job.salary}</dd></div><div><dt>经验 / 学历</dt><dd>{job.experience} / {job.education}</dd></div><div><dt>用工性质</dt><dd>{job.type.includes("临时") ? "临时用工" : "正式用工"}</dd></div><div><dt>班次</dt><dd>两班倒 · 月休 4 天</dd></div></dl></div></div><div className="risk-box"><div><span>⚠</span><div><b>AI 合规与质量检查</b><p>发现原文职责不完整、薪资口径需确认；涉及年龄或个人条件时不得作为 AI 自动淘汰依据。</p></div></div><em>需人工复核</em></div><div className="rationale"><b>本次优化依据</b><span>统一岗位命名</span><span>结构化薪资</span><span>补全班次信息</span><span>移除歧视性表达</span></div><div className="workbench-actions"><button className="outline" onClick={() => onNotify("已保存人工修改草稿")}>编辑岗位</button><button className="primary" onClick={onApprove}>✓ 人工确认并发布</button></div></article>;
}

function CandidateEvidence({ candidate, onSchedule }: { candidate: Candidate; onSchedule: () => void }) {
  return <article className="panel evidence-panel"><div className="evidence-score"><div className="score-ring"><span>{candidate.score}</span><small>/ 100</small></div><div><p className="eyebrow">EXPLAINABLE MATCH</p><h2>{candidate.name} × {candidate.role}</h2><p>综合硬条件、经历相关度与到岗可行性；最终决定需人工确认。</p></div><button className="primary" onClick={onSchedule}>安排面试</button></div><div className="evidence-grid"><div><h3>匹配证据</h3>{candidate.evidence.map((item) => <p key={item}><span>✓</span>{item}</p>)}</div><div><h3>待确认缺口</h3><p className="gap"><span>!</span>{candidate.gap}</p><p className="gap"><span>!</span>请核验证书原件与有效期</p></div><div><h3>评分构成</h3><p><span>硬条件</span><b>36 / 40</b></p><p><span>技能经历</span><b>32 / 35</b></p><p><span>到岗适配</span><b>24 / 25</b></p></div></div></article>;
}

function Screening({ candidate, step, setStep, onSchedule }: { candidate: Candidate; step: number; setStep: (n: number) => void; onSchedule: () => void }) {
  const questions = ["请确认你是否持有有效的低压电工证？", "你能否接受生产旺季两班倒的工作安排？", "如果面试通过，最快什么时候可以到岗？"];
  return <section className="page screening-page"><div className="page-heading"><div><p className="eyebrow">AI SCREENING</p><h1>结构化 AI 初筛</h1><p>只询问岗位必要信息，敏感问题自动拦截，所有结论等待人工终审。</p></div><span className="privacy-chip">盾 隐私脱敏已开启</span></div><div className="screen-layout"><article className="panel conversation"><div className="conversation-head"><span className="avatar">{candidate.initials}</span><div><b>{candidate.name}</b><small>{candidate.role} · 匹配分 {candidate.score}</small></div><span className="live"><i /> AI 初筛中</span></div><div className="messages"><div className="message ai"><span>AI</span><div><p>你好，{candidate.name.slice(0, 1)}先生。接下来有 3 个与岗位直接相关的问题，预计 2 分钟完成。你的回答仅用于本次招聘评估。</p><small>10:24</small></div></div>{questions.slice(0, step).map((question, index) => <div key={question}><div className="message ai"><span>AI</span><div><p>{question}</p><small>10:{25 + index * 2}</small></div></div>{index < step - 1 && <div className="message human"><div><p>{index === 0 ? "有，证书到 2028 年有效，可以面试时带原件。" : "可以接受倒班，我上一份工作也是两班倒。"}</p><small>10:{26 + index * 2}</small></div></div>}</div>)}</div><div className="quick-replies">{step < 3 ? <><button onClick={() => setStep(step + 1)}>可以 / 是</button><button onClick={() => setStep(step + 1)}>需要说明</button><button onClick={() => setStep(step + 1)}>申请人工沟通</button></> : <button className="primary" onClick={onSchedule}>完成初筛并提交人工复核</button>}</div></article><aside className="panel screening-summary"><p className="eyebrow">LIVE SUMMARY</p><h2>实时结构化摘要</h2><div className="progress"><span>初筛进度</span><b>{step} / 3</b><i><em style={{ width: `${step / 3 * 100}%` }} /></i></div><dl><div><dt>必要证书</dt><dd className={step > 1 ? "ok" : "pending"}>{step > 1 ? "✓ 已确认" : "待回答"}</dd></div><div><dt>班次意愿</dt><dd className={step > 2 ? "ok" : "pending"}>{step > 2 ? "✓ 可接受" : "待回答"}</dd></div><div><dt>最快到岗</dt><dd className="pending">待回答</dd></div></dl><div className="guardrail"><b>安全护栏</b><p>不会询问婚育、民族、健康史等非岗位必要信息。</p></div><div className="human-note"><b>给招聘专员的提示</b><p>{candidate.gap}。证书原件需要在面试阶段由人工核验。</p></div></aside></div></section>;
}
