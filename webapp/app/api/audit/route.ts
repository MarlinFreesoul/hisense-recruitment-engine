// 本地 vite dev 无 cloudflare:workers 模块，@vite-ignore 降级为 offline-demo；Cloudflare 部署时正常解析
// 用变量承载 specifier，避免 Rolldown 构建期静态解析（仍保留运行时动态 import + 降级）
let env: any = { DB: undefined };
try {
  const cfSpec = "cloudflare:workers";
  const mod = await import(/* @vite-ignore */ cfSpec);
  env = mod.env;
} catch {
  env = { DB: undefined };
}

const CREATE_SQL = `CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  actor TEXT NOT NULL DEFAULT 'demo-recruiter',
  detail TEXT,
  created_at TEXT NOT NULL
)`;

export async function GET() {
  if (!env.DB) return Response.json({ records: [], mode: "offline-demo" });
  await env.DB.prepare(CREATE_SQL).run();
  const records = await env.DB.prepare("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 50").all();
  return Response.json({ records: records.results, mode: "persistent" });
}

export async function POST(request: Request) {
  const body = await request.json() as { action?: string; entityType?: string; entityId?: string; detail?: string };
  if (!body.action || !body.entityType || !body.entityId) return Response.json({ error: "缺少必要字段" }, { status: 400 });
  if (!env.DB) return Response.json({ ok: true, mode: "offline-demo" });
  await env.DB.prepare(CREATE_SQL).run();
  await env.DB.prepare("INSERT INTO audit_logs (action, entity_type, entity_id, actor, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)")
    .bind(body.action, body.entityType, body.entityId, "demo-recruiter", body.detail ?? null, new Date().toISOString()).run();
  return Response.json({ ok: true, mode: "persistent" });
}
