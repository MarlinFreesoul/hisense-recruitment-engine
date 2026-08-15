import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const pageUrl = new URL("../app/page.tsx", import.meta.url);
const layoutUrl = new URL("../app/layout.tsx", import.meta.url);
const cssUrl = new URL("../app/globals.css", import.meta.url);
const dataUrl = new URL("../public/data/hisense_boss_jobs_structured.md", import.meta.url);

test("implements the complete recruitment workflow", async () => {
  const page = await readFile(pageUrl, "utf8");
  for (const label of ["运营驾驶舱", "岗位治理", "人才匹配", "AI 初筛", "人工确认并发布", "安排面试"]) {
    assert.match(page, new RegExp(label));
  }
  assert.match(page, /规则校验＋语义匹配＋人工终审/);
  assert.match(page, /不会询问婚育、民族、健康史/);
});

test("bundles all 115 source jobs and production metadata", async () => {
  const [data, layout, css] = await Promise.all([
    readFile(dataUrl, "utf8"), readFile(layoutUrl, "utf8"), readFile(cssUrl, "utf8"),
  ]);
  const rows = data.split(/\r?\n/).filter((line) => /^\|\s*\d+\s*\|/.test(line));
  assert.equal(rows.length, 115);
  assert.match(layout, /海信招聘运营智能体/);
  assert.match(layout, /og\.jpg/);
  assert.match(css, /@media\(max-width:700px\)/);
});
