const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.author = "DevCycle AI";
pres.company = "DevCycle AI";
pres.theme = { headFontFace: "Calibri", bodyFontFace: "Calibri" };

// ---- palette --------------------------------------------------------------
const P = {
  ink: "0A0E1A", ink2: "141A2E", white: "FFFFFF", panel: "F3F5FB",
  panel2: "ECF0FA", line: "E2E7F2", text: "1C2233", sub: "4A5268",
  muted: "8793A6",
  purple: "7C5CFF", purpleD: "5B3FD6", blue: "3E8BFF", green: "17A34A",
  amber: "E08A00", red: "E4484D", teal: "0E9FA0",
};
const HEAD = "Calibri", BODY = "Calibri";

// ---- helpers --------------------------------------------------------------
function shadow() { return { type: "outer", color: "9AA6BE", blur: 9, offset: 3, angle: 90, opacity: 0.33 }; }

function kickerTitle(slide, kicker, title, opt = {}) {
  const dark = opt.dark;
  slide.addText(kicker.toUpperCase(), {
    x: 0.6, y: 0.42, w: 12.1, h: 0.3, fontFace: HEAD, fontSize: 12, bold: true,
    color: dark ? P.blue : P.purple, charSpacing: 2, align: "left", isTextBox: true, margin: 0,
  });
  slide.addText(title, {
    x: 0.6, y: 0.72, w: 12.1, h: 0.75, fontFace: HEAD, fontSize: 30, bold: true,
    color: dark ? P.white : P.text, align: "left", isTextBox: true, margin: 0,
  });
}

function bullets(slide, items, o) {
  const runs = items.map((it, i) => ({
    text: it.t,
    options: {
      bullet: { indent: 16 }, breakLine: true,
      color: it.c || o.color || P.sub, fontFace: BODY,
      fontSize: o.fontSize || 15, bold: !!it.b,
      paraSpaceAfter: o.gap != null ? o.gap : 9,
    },
  }));
  slide.addText(runs, { x: o.x, y: o.y, w: o.w, h: o.h, align: "left", valign: "top", isTextBox: true, margin: 0 });
}

function card(slide, o) {
  slide.addShape(pres.ShapeType.roundRect, {
    x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.1,
    fill: { color: o.fill || P.panel }, line: { color: o.line || P.line, width: 1 },
    shadow: shadow(),
  });
  if (o.accent) {
    slide.addShape(pres.ShapeType.ellipse, { x: o.x + 0.25, y: o.y + 0.25, w: 0.5, h: 0.5, fill: { color: o.accent }, line: { color: o.accent, width: 0 } });
    slide.addText(o.badge || "", { x: o.x + 0.25, y: o.y + 0.25, w: 0.5, h: 0.5, align: "center", valign: "middle", color: "FFFFFF", bold: true, fontSize: o.badgeSize || 16, fontFace: HEAD, isTextBox: true, margin: 0 });
  }
  const tx = o.accent ? o.x + 0.95 : o.x + 0.3;
  const tw = o.accent ? o.w - 1.2 : o.w - 0.6;
  slide.addText(o.title, { x: tx, y: o.y + 0.26, w: tw, h: 0.4, fontFace: HEAD, fontSize: o.titleSize || 15, bold: true, color: P.text, align: "left", isTextBox: true, margin: 0 });
  if (o.bodyRuns) {
    slide.addText(o.bodyRuns, { x: o.x + 0.3, y: o.y + 0.78, w: o.w - 0.6, h: o.h - 1.0, fontFace: BODY, fontSize: o.bodySize || 12.5, color: P.sub, align: "left", valign: "top", isTextBox: true, margin: 0 });
  } else if (o.body) {
    slide.addText(o.body, { x: o.x + 0.3, y: o.y + (o.accent ? 0.86 : 0.74), w: o.w - 0.6, h: o.h - 1.0, fontFace: BODY, fontSize: o.bodySize || 12.5, color: P.sub, align: "left", valign: "top", isTextBox: true, margin: 0 });
  }
}

function stat(slide, o) {
  slide.addShape(pres.ShapeType.roundRect, { x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.1, fill: { color: o.fill || P.panel }, line: { color: o.line || P.line, width: 1 }, shadow: shadow() });
  slide.addText(o.value, { x: o.x + 0.15, y: o.y + 0.22, w: o.w - 0.3, h: 0.7, fontFace: HEAD, fontSize: o.size || 33, bold: true, color: o.color || P.purple, align: "center", isTextBox: true, margin: 0 });
  slide.addText(o.label, { x: o.x + 0.2, y: o.y + 0.95, w: o.w - 0.4, h: o.h - 1.05, fontFace: BODY, fontSize: 12, color: P.sub, align: "center", valign: "top", isTextBox: true, margin: 0 });
}

function note(slide, t) { slide.addNotes(t); }

// ---- masters --------------------------------------------------------------
const foot = (c) => ({ text: { text: "DevCycle AI  ·  Agentic SDLC Automation", options: { x: 0.6, y: 7.08, w: 9, h: 0.3, fontSize: 9, color: c, fontFace: BODY, align: "left", isTextBox: true, margin: 0 } } });
pres.defineSlideMaster({ title: "COVER", background: { color: P.ink } });
pres.defineSlideMaster({ title: "LIGHT", background: { color: P.white }, objects: [foot("9AA3B2")], slideNumber: { x: 12.5, y: 7.08, w: 0.7, h: 0.3, fontSize: 9, color: "9AA3B2", align: "right", fontFace: BODY } });
pres.defineSlideMaster({ title: "DARK", background: { color: P.ink }, objects: [foot("5B6478")], slideNumber: { x: 12.5, y: 7.08, w: 0.7, h: 0.3, fontSize: 9, color: "5B6478", align: "right", fontFace: BODY } });

const EST = "Figures are illustrative estimates; actual results vary by team, scope and codebase.";

// ==========================================================================
// 1 — COVER
// ==========================================================================
let s = pres.addSlide({ masterName: "COVER" });
// decorative rings (translucent)
s.addShape(pres.ShapeType.ellipse, { x: 9.3, y: 0.7, w: 4.6, h: 4.6, fill: { color: P.purple, transparency: 90 }, line: { color: P.purple, width: 1.5, transparency: 55 } });
s.addShape(pres.ShapeType.ellipse, { x: 10.5, y: 1.9, w: 2.9, h: 2.9, fill: { color: P.blue, transparency: 88 }, line: { color: P.blue, width: 1.5, transparency: 55 } });
s.addShape(pres.ShapeType.ellipse, { x: 11.35, y: 2.75, w: 1.2, h: 1.2, fill: { color: P.purple, transparency: 45 }, line: { color: P.purple, width: 0 } });
s.addText("</>  ∞", { x: 10.95, y: 2.95, w: 2, h: 0.8, fontFace: "Consolas", fontSize: 24, bold: true, color: "FFFFFF", align: "center", isTextBox: true, margin: 0 });
s.addText("AGENTIC SDLC AUTOMATION", { x: 0.7, y: 1.95, w: 8.6, h: 0.4, fontFace: HEAD, fontSize: 14, bold: true, color: P.blue, charSpacing: 3, isTextBox: true, margin: 0 });
s.addText("DevCycle AI", { x: 0.62, y: 2.35, w: 9, h: 1.3, fontFace: HEAD, fontSize: 66, bold: true, color: "FFFFFF", isTextBox: true, margin: 0 });
s.addText("Automating the Software Development Lifecycle through Agentic AI", { x: 0.7, y: 3.65, w: 8.6, h: 0.7, fontFace: BODY, fontSize: 19, color: "C7CEDC", isTextBox: true, margin: 0 });
s.addText([
  { text: "Offline", options: { color: P.purple, bold: true } }, { text: "   ·   ", options: { color: "5B6478" } },
  { text: "Edge-ready", options: { color: P.blue, bold: true } }, { text: "   ·   ", options: { color: "5B6478" } },
  { text: "Confidential", options: { color: P.teal, bold: true } },
], { x: 0.7, y: 4.5, w: 8.6, h: 0.4, fontFace: HEAD, fontSize: 16, isTextBox: true, margin: 0 });
s.addText("Tool · Technology · Agents · LLM communication · Business impact · Future scope", { x: 0.7, y: 6.35, w: 11.8, h: 0.4, fontFace: BODY, fontSize: 12, italic: true, color: "8793A6", isTextBox: true, margin: 0 });
note(s, "DevCycle AI is an offline, edge-ready agentic SDLC automation tool. This deck covers the tool, technology, agents, how agents talk to the LLM, challenges resolved, business impact, and future scope.");

// ==========================================================================
// 2 — EXECUTIVE SUMMARY
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Executive Summary", "One instruction in — a complete, verified delivery out");
bullets(s, [
  { t: "Describe the software (instruction + input/output expectations), pick the agents, and run.", b: false },
  { t: "Three AI agents — Architect, Developer, Validation Engineer — produce the whole delivery." },
  { t: "Outputs: architecture + 5 diagrams, source code, unit & integration tests, static analysis, coverage, and an Excel validation report." },
  { t: "Runs fully offline on edge devices, works behind corporate proxies, and keeps every artifact local and confidential." },
  { t: "Pluggable brain: local GGUF model, a local OpenAI-compatible endpoint (Ollama / LM Studio), or a zero-model deterministic engine." },
], { x: 0.6, y: 1.75, w: 7.7, h: 4.8, fontSize: 15.5, gap: 12 });
stat(s, { x: 8.7, y: 1.8, w: 4.0, h: 1.45, value: "50–65%", label: "faster end-to-end delivery", color: P.purple });
stat(s, { x: 8.7, y: 3.45, w: 4.0, h: 1.45, value: "40–55%", label: "lower engineering effort cost", color: P.green });
stat(s, { x: 8.7, y: 5.1, w: 4.0, h: 1.4, value: "100%", label: "offline / on-prem — zero data egress", color: P.blue });
note(s, "The core promise: turn a plain-language request into architecture, code, tests, validation and reports — fully offline.");

// ==========================================================================
// 3 — THE CHALLENGE
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "The Challenge", "Why delivering quality software is slow and risky");
const ch = [
  ["01", P.amber, "Manual SDLC artifacts", "Architecture docs, design, tests and reports take days of repetitive engineering effort."],
  ["02", P.amber, "Inconsistent & untraceable", "Docs drift, traceability is missing — audits and impact analysis are painful."],
  ["03", P.red, "Tests & validation skipped", "Under deadline pressure, quality steps are cut, raising defect and rework risk."],
  ["04", P.red, "Cloud AI is off-limits", "Confidential / air-gapped code can't be sent to cloud AI tools for help."],
  ["05", P.blue, "Fragmented per language", "Tooling and quality bars vary by language and framework across teams."],
  ["06", P.blue, "Slow standardization", "Onboarding and consistent practices across projects take a long time."],
];
let cx = 0.6, cy = 1.8, cw = 3.95, chh = 2.2, gapx = 0.2, gapy = 0.25;
ch.forEach((c, i) => {
  const col = i % 3, row = Math.floor(i / 3);
  card(s, { x: cx + col * (cw + gapx), y: cy + row * (chh + gapy), w: cw, h: chh, accent: c[1], badge: c[0], badgeSize: 13, title: c[2], body: c[3], titleSize: 14.5, bodySize: 12 });
});
note(s, "The pain: slow manual artifacts, inconsistency, skipped validation, inability to use cloud AI on sensitive code, and fragmented, slow standardization.");

// ==========================================================================
// 4 — THE SOLUTION
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "The Solution", "DevCycle AI — agentic delivery you can trust");
bullets(s, [
  { t: "One instruction becomes a complete, traceable delivery in minutes." },
  { t: "A deterministic offline engine guarantees runnable output — even with no model." },
  { t: "Every artifact is linked: Architecture ID → Design ID → Code → Test." },
  { t: "Built-in validation executes tests, static analysis and coverage, then an Excel report." },
  { t: "Security-first: offline-only mode, local encrypted storage, proxy-aware." },
], { x: 0.6, y: 1.75, w: 7.5, h: 4.6, fontSize: 16, gap: 14 });
// 3-agent mini pipeline on right
const pipe = [["A", P.purple, "Architect"], ["D", P.blue, "Developer"], ["V", P.green, "Validation"]];
let py = 1.95;
pipe.forEach((p, i) => {
  s.addShape(pres.ShapeType.roundRect, { x: 8.7, y: py, w: 4.0, h: 1.15, rectRadius: 0.1, fill: { color: P.panel }, line: { color: P.line, width: 1 }, shadow: shadow() });
  s.addShape(pres.ShapeType.ellipse, { x: 8.95, y: py + 0.3, w: 0.55, h: 0.55, fill: { color: p[1] } });
  s.addText(p[0], { x: 8.95, y: py + 0.3, w: 0.55, h: 0.55, align: "center", valign: "middle", color: "FFFFFF", bold: true, fontSize: 18, fontFace: HEAD, isTextBox: true, margin: 0 });
  s.addText(p[2], { x: 9.7, y: py + 0.32, w: 2.8, h: 0.5, fontFace: HEAD, fontSize: 16, bold: true, color: P.text, valign: "middle", isTextBox: true, margin: 0 });
  if (i < 2) s.addText("▼", { x: 10.4, y: py + 1.12, w: 0.6, h: 0.3, align: "center", color: P.sub, fontSize: 12, isTextBox: true, margin: 0 });
  py += 1.55;
});
note(s, "DevCycle AI resolves the pain with a fast, deterministic, traceable, validated and secure agentic pipeline.");

// ==========================================================================
// 5 — TOOL OVERVIEW & CAPABILITIES
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Tool Overview", "What the tool does, end to end");
bullets(s, [
  { t: "Plain-language input: instruction, input & output expectations.", b: true },
  { t: "Select which agents run; per-agent configuration for each." },
  { t: "Live preview of generated roles, tasks and prompts." },
  { t: "Offline English audio narration of the agentic flow (with captions)." },
  { t: "Settings: LLM backend, language & framework, timezone, security." },
], { x: 0.6, y: 1.75, w: 5.9, h: 4.6, fontSize: 15 });
bullets(s, [
  { t: "Local, confidential artifact store (owner-only, optional AES-GCM).", b: true },
  { t: "Excel validation workbook: Summary, Functional, NonFunctional, Architecture, TestResults, CodeQuality, DevMetrics." },
  { t: "Timezone-correct, labelled timestamps on every document." },
  { t: "Download all generated artifacts as a single archive." },
  { t: "No external communication by the core flow." },
], { x: 6.9, y: 1.75, w: 5.9, h: 4.6, fontSize: 15 });
note(s, "Capabilities span input, agent selection/config, preview, narration, confidential storage, Excel reporting and export.");

// ==========================================================================
// 6 — TECHNOLOGY STACK
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Technology Used", "A dependency-light, pure-Python core");
const tech = [
  [P.purple, "User interface", "Streamlit (telemetry off, localhost-bound)."],
  [P.blue, "LLM backends", "llama-cpp-python (GGUF), OpenAI-compatible HTTP (Ollama / LM Studio / vLLM), deterministic offline engine."],
  [P.teal, "Code generation", "Per-language generators: Python, C, C++, Java, Rust, Kotlin."],
  [P.green, "Testing & coverage", "pytest, cargo test, JUnit/TestNG+JaCoCo, Kotest/Gradle+Kover, GoogleTest/CTest; Python coverage via stdlib tracer."],
  [P.amber, "Quality & docs", "AST/regex code model, Mermaid diagrams, SonarQube-style static analysis, openpyxl Excel, Markdown."],
  [P.purpleD, "Security & runtime", "cryptography (AES-GCM) + fallback cipher, proxy-aware stdlib HTTP, pyttsx3 offline TTS, Python 3.9+."],
];
let tx = 0.6, ty = 1.8, tw = 3.95, th = 2.2;
tech.forEach((t, i) => {
  const col = i % 3, row = Math.floor(i / 3);
  card(s, { x: tx + col * (tw + 0.2), y: ty + row * (th + 0.25), w: tw, h: th, accent: t[0], badge: "", title: t[1], body: t[2], titleSize: 15, bodySize: 12 });
});
note(s, "Streamlit UI, pluggable LLM backends, per-language code generation, native test/coverage tools, quality tooling, Excel reporting, and local security — all dependency-light.");

// ==========================================================================
// 7 — THE THREE AGENTS
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Agent Information", "Three specialist agents, one delivery");
const agents = [
  [P.purple, "A", "Software Architect", "Turns requirements into a Software Architecture Document with 5 diagrams (overall, component, data-flow, sequence, use-case), NFR tactics, decision records, risks and traceability."],
  [P.blue, "D", "Software Developer", "Component design + class/sequence diagrams from the actual code; source, unit & integration tests (and runs them); static analysis, coverage, and design-ID banners in the code."],
  [P.green, "V", "Validation Engineer", "Independently verifies functional & non-functional requirements, validates architecture/design, re-runs the tests, and compiles the Excel validation report (incl. DevMetrics)."],
];
let ax = 0.6, aw = 4.0, ah = 4.3;
agents.forEach((a, i) => {
  card(s, { x: ax + i * (aw + 0.2), y: 1.85, w: aw, h: ah, accent: a[0], badge: a[1], badgeSize: 18, title: a[2], body: a[3], titleSize: 16, bodySize: 13 });
});
note(s, "Architect designs, Developer builds and tests, Validation Engineer independently verifies and reports.");

// ==========================================================================
// 8 — AGENT SKILLS
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Agent Skills & Capabilities", "What each agent is good at");
bullets(s, [
  { t: "Deterministic requirement analysis → roles, tasks & prompts per agent.", b: true },
  { t: "Multi-language, idiomatic code with framework-correct tests." },
  { t: "Code-grounded class & sequence diagrams; design-pattern detection." },
  { t: "End-to-end traceability: Architecture ID → Design ID → Code → Test." },
], { x: 0.6, y: 1.75, w: 5.9, h: 4.6, fontSize: 15 });
bullets(s, [
  { t: "SonarQube-style static analysis, ranked by severity.", b: true },
  { t: "Real code coverage for unit & integration suites, where toolchain is present." },
  { t: "Robust toolchain detection (PATH, *_HOME, project wrappers)." },
  { t: "LLM-mode safety: validate output, else fall back to a guaranteed-runnable scaffold." },
], { x: 6.9, y: 1.75, w: 5.9, h: 4.6, fontSize: 15 });
note(s, "Agents combine deterministic analysis, multi-language generation, code-grounded diagrams, traceability, static analysis, coverage and safe LLM fallback.");

// ==========================================================================
// 9 — AGENTS <-> LLM COMMUNICATION
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Agents ↔ LLM Communication", "How agents talk to the model — safely");
const steps = [
  ["1", P.purple, "Analyse", "Instruction + I/O → ProjectSpec (components, operations, FRs/NFRs)."],
  ["2", P.purple, "Build prompt", "Role system prompt + user prompt + compact JSON context block."],
  ["3", P.blue, "Select backend", "Local GGUF · OpenAI-compatible endpoint (Ollama) · Offline engine."],
  ["4", P.blue, "Parse & validate", "Extract file blocks / markdown; check syntax & structure."],
  ["5", P.green, "Fallback", "Invalid or failing output → deterministic, runnable scaffold."],
  ["6", P.green, "Persist", "Write artifacts to the local, confidential store."],
];
let sx = 0.6, sw = 3.95, sh = 1.75;
steps.forEach((st, i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const x = sx + col * (sw + 0.2), y = 1.8 + row * (sh + 0.35);
  card(s, { x, y, w: sw, h: sh, accent: st[1], badge: st[0], badgeSize: 14, title: st[2], body: st[3], titleSize: 14.5, bodySize: 11.5 });
  if (col < 2) s.addText("▶", { x: x + sw - 0.02, y: y + sh / 2 - 0.15, w: 0.24, h: 0.3, align: "center", valign: "middle", color: P.sub, fontSize: 13, isTextBox: true, margin: 0 });
});
s.addText([
  { text: "Guardrails:  ", options: { bold: true, color: P.text } },
  { text: "offline-only mode blocks all network backends · reports name the real model/endpoint (e.g. gemma4:e4b @ 127.0.0.1:11434) · no data leaves the device.", options: { color: P.sub } },
], { x: 0.6, y: 6.25, w: 12.1, h: 0.5, fontFace: BODY, fontSize: 12.5, align: "left", isTextBox: true, margin: 0 });
note(s, "Agents ground the model with a JSON ProjectSpec, choose a backend, parse and validate the response, and fall back to a deterministic scaffold if needed — all on-device.");

// ==========================================================================
// 10 — MULTI-LANGUAGE SUPPORT (table)
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Multi-Language Support", "Six languages, framework-correct tests & coverage");
const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: P.purpleD }, fontFace: HEAD, fontSize: 14, align: "left", valign: "middle" } });
const cell = (t) => ({ text: t, options: { color: P.text, fontFace: BODY, fontSize: 13.5, align: "left", valign: "middle" } });
const rows = [
  [hdr("Language"), hdr("Default framework"), hdr("Alternatives"), hdr("Coverage tool")],
  [cell("Python"), cell("pytest"), cell("unittest"), cell("stdlib tracer (UT + IT)")],
  [cell("Rust"), cell("cargo test"), cell("—"), cell("cargo-llvm-cov / tarpaulin")],
  [cell("Java"), cell("JUnit 5"), cell("JUnit 4, TestNG"), cell("JaCoCo")],
  [cell("Kotlin"), cell("Kotest"), cell("JUnit 5"), cell("Kover")],
  [cell("C"), cell("GoogleTest"), cell("—"), cell("gcovr / lcov")],
  [cell("C++"), cell("GoogleTest"), cell("Catch2"), cell("gcovr / lcov")],
];
s.addTable(rows, { x: 0.6, y: 1.9, w: 12.1, colW: [2.6, 3.3, 3.2, 3.0], rowH: 0.56, border: { type: "solid", color: P.line, pt: 1 }, align: "left", valign: "middle", fontFace: BODY, fill: { color: P.white } });
// zebra
note(s, "Python, Rust, Java, Kotlin, C and C++ — each with its default and alternative unit-test frameworks and its standard coverage tool.");

// ==========================================================================
// 11 — ENGINEERING RIGOR
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Engineering Rigor & Quality", "Delivery that stands up to review");
bullets(s, [
  { t: "Architecture doc always carries 5 Mermaid diagrams (validated & auto-sanitized)." },
  { t: "Class & sequence diagrams derived from the actual generated code." },
  { t: "Design patterns and detailed component descriptions." },
  { t: "Design-ID banners in code; 'Covers:' links from tests back to design & requirements." },
  { t: "Static analysis summarized by severity; coverage reported per suite." },
  { t: "Generated projects are real, idiomatic, buildable projects — not snippets." },
], { x: 0.6, y: 1.8, w: 12.0, h: 4.8, fontSize: 16, gap: 13 });
note(s, "Diagrams, traceability, patterns, static analysis and coverage make every delivery review- and audit-ready.");

// ==========================================================================
// 12 — SECURITY (dark)
// ==========================================================================
s = pres.addSlide({ masterName: "DARK" });
kickerTitle(s, "Security & Confidentiality", "Built for secure, air-gapped environments", { dark: true });
const sec = [
  "Fully offline core — no external communication.",
  "Offline-only mode hard-blocks every network backend.",
  "Local, owner-only artifact storage; optional AES-GCM encryption at rest.",
  "Corporate-proxy aware; runs air-gapped on the edge.",
  "No in-app model download — GGUF models placed out of band.",
  "Streamlit telemetry disabled; binds to localhost by default.",
];
s.addText(sec.map((t) => ({ text: t, options: { bullet: { indent: 16 }, breakLine: true, color: "D7DCEA", fontFace: BODY, fontSize: 16.5, paraSpaceAfter: 13 } })),
  { x: 0.6, y: 1.9, w: 12.0, h: 4.8, align: "left", valign: "top", isTextBox: true, margin: 0 });
note(s, "Confidentiality by design: offline-only, local encrypted storage, proxy-aware, no telemetry, no model download in-app.");

// ==========================================================================
// 13 — CHALLENGES -> RESOLUTION (table)
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Challenges → Resolution", "How DevCycle AI turns each challenge into an outcome");
const H = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: P.text }, fontFace: HEAD, fontSize: 13.5, valign: "middle" } });
const Lc = (t) => ({ text: t, options: { color: P.text, bold: true, fontFace: BODY, fontSize: 12.5, valign: "middle" } });
const Rc = (t) => ({ text: t, options: { color: P.sub, fontFace: BODY, fontSize: 12.5, valign: "middle" } });
const crows = [
  [H("Challenge"), H("How DevCycle AI resolves it")],
  [Lc("Manual, slow SDLC artifacts"), Rc("One instruction → full delivery (docs, code, tests, reports) in minutes.")],
  [Lc("Inconsistent docs / no traceability"), Rc("Standardized documents + Architecture → Design → Code → Test matrix.")],
  [Lc("Tests & validation skipped"), Rc("Auto-generated & executed tests, static analysis, coverage and an Excel report.")],
  [Lc("Cloud AI unusable on sensitive code"), Rc("Fully offline, on-prem / edge, encrypted local storage — zero egress.")],
  [Lc("Fragmented per-language quality"), Rc("Uniform generators + framework-correct tests across six languages.")],
  [Lc("Unreliable raw LLM output"), Rc("Validate, then fall back to a deterministic, runnable scaffold.")],
  [Lc("Slow onboarding & standardization"), Rc("Consistent, explainable artifacts + a narrated agentic flow.")],
];
s.addTable(crows, { x: 0.6, y: 1.85, w: 12.1, colW: [4.3, 7.8], rowH: 0.5, border: { type: "solid", color: P.line, pt: 1 }, align: "left", valign: "middle", fontFace: BODY });
note(s, "Each named challenge maps to a concrete capability that resolves it.");

// ==========================================================================
// 14 — BUSINESS IMPACT: TIME (chart)
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Business Impact — Time Saving", "Where the hours come back");
const chartData = [{
  name: "Estimated time reduction",
  labels: ["Overall cycle", "Validation & reporting", "Architecture doc", "Component design", "Code + unit tests", "Integration tests"],
  values: [58, 85, 78, 72, 66, 60],
}];
s.addChart(pres.ChartType.bar, chartData, {
  x: 0.55, y: 1.8, w: 8.2, h: 4.9, barDir: "bar", chartColors: [P.purple],
  showTitle: false, showLegend: false,
  showValue: true, dataLabelPosition: "outEnd", dataLabelColor: P.text, dataLabelFontFace: "+mn-lt", dataLabelFontSize: 12, dataLabelFormatCode: '0"%"',
  valAxisMinVal: 0, valAxisMaxVal: 100, valAxisMajorUnit: 20,
  catAxisLabelColor: P.text, catAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 12,
  valAxisLabelColor: P.sub, valAxisLabelFontFace: "+mn-lt", valAxisLabelFontSize: 11, valAxisLabelFormatCode: '0"%"',
  valGridLine: { color: P.line, size: 1 }, catGridLine: { style: "none" },
});
stat(s, { x: 9.1, y: 1.85, w: 3.6, h: 1.5, value: "~55%", label: "faster component delivery", color: P.purple });
bullets(s, [
  { t: "Drafting SAD, design & tests is near-instant vs. days." },
  { t: "Agents parallelize design, build and validation." },
  { t: "Traceability cuts rework and impact-analysis time." },
], { x: 9.1, y: 3.6, w: 3.7, h: 2.8, fontSize: 13.5, gap: 10 });
s.addText(EST, { x: 0.6, y: 6.75, w: 12.1, h: 0.3, fontFace: BODY, fontSize: 10, italic: true, color: P.muted, isTextBox: true, margin: 0 });
note(s, "Time savings are largest in documentation, validation and reporting; overall component cycle time drops roughly by half.");

// ==========================================================================
// 15 — BUSINESS IMPACT: COST & VALUE
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Business Impact — Cost & Value", "Lower cost, higher quality, less risk");
stat(s, { x: 0.6, y: 1.8, w: 3.85, h: 1.5, value: "40–55%", label: "lower engineering effort cost", color: P.green });
stat(s, { x: 4.67, y: 1.8, w: 3.85, h: 1.5, value: "80–90%", label: "less time on docs & reports", color: P.purple });
stat(s, { x: 8.75, y: 1.8, w: 3.95, h: 1.5, value: "Hours→Min", label: "audit & traceability prep", color: P.blue });
bullets(s, [
  { t: "Quality: consistent tests, coverage & traceability → fewer defects and less rework.", b: true },
  { t: "Compliance: built-in validation and auditable traceability out of the box." },
  { t: "Risk: usable in secure / air-gapped environments — no data egress or vendor exposure." },
  { t: "Standardization: uniform artifacts raise the quality floor across every team." },
  { t: "Onboarding: new engineers ramp faster on explainable, narrated deliveries." },
  { t: "Vendor cost: local / open models — no per-seat cloud-AI subscription fees." },
], { x: 0.6, y: 3.6, w: 12.1, h: 3.0, fontSize: 15, gap: 10 });
s.addText(EST, { x: 0.6, y: 6.78, w: 12.1, h: 0.3, fontFace: BODY, fontSize: 10, italic: true, color: P.muted, isTextBox: true, margin: 0 });
note(s, "Beyond time: cost, quality, compliance, risk reduction, standardization, faster onboarding and no cloud-AI licensing.");

// ==========================================================================
// 16 — FUTURE SCOPE
// ==========================================================================
s = pres.addSlide({ masterName: "LIGHT" });
kickerTitle(s, "Future Scope", "Toward repo-native, memory-and-skill-aware agents");
const fut = [
  [P.purple, "Repo-native deployment", "Install DevCycle AI directly on specific repositories and run in place."],
  [P.blue, "Repo memory", "Index the repo (code, conventions, history) so agents ground output in the actual codebase."],
  [P.teal, "Repo skills", "Learn repo-specific patterns, standards and review rules — then reuse them automatically."],
  [P.green, "CI/CD & PR integration", "Run on pull requests, autofix, and post validation reports back to the PR."],
  [P.amber, "Human-in-the-loop", "Multi-agent collaboration with review checkpoints and approvals."],
  [P.purpleD, "Models & coverage", "Fine-tuned small local models per org; split UT/IT coverage on the JVM; wider language support."],
];
let fx = 0.6, fw = 3.95, fh = 2.15;
fut.forEach((f, i) => {
  const col = i % 3, row = Math.floor(i / 3);
  card(s, { x: fx + col * (fw + 0.2), y: 1.85 + row * (fh + 0.25), w: fw, h: fh, accent: f[0], badge: "", title: f[1], body: f[2], titleSize: 14.5, bodySize: 12 });
});
note(s, "The roadmap makes the tool repo-native: deployed on a repo, with memory and skills of that repo, integrated into CI/CD and PRs, with better models and coverage.");

// ==========================================================================
// 17 — SUMMARY (dark) — the solution in bullet points
// ==========================================================================
s = pres.addSlide({ masterName: "DARK" });
kickerTitle(s, "Summary", "The solution — in bullet points", { dark: true });
const sumL = [
  "Offline, edge-ready, confidential agentic SDLC automation.",
  "Three agents: Architect, Developer, Validation Engineer.",
  "Full delivery: architecture + diagrams, code, tests, static analysis, coverage, Excel report.",
  "Six languages with framework-correct tests and real coverage.",
];
const sumR = [
  "End-to-end traceability + validation, out of the box.",
  "Pluggable local LLM or a zero-model deterministic engine.",
  "~50–65% faster · 40–55% lower effort cost · 100% on-prem.",
  "Roadmap: repo-native memory & skills, CI/CD integration.",
];
const mk = (arr, c) => arr.map((t) => ({ text: t, options: { bullet: { indent: 16 }, breakLine: true, color: "D7DCEA", fontFace: BODY, fontSize: 15.5, paraSpaceAfter: 14 } }));
s.addText(mk(sumL), { x: 0.6, y: 1.95, w: 6.0, h: 4.4, align: "left", valign: "top", isTextBox: true, margin: 0 });
s.addText(mk(sumR), { x: 6.8, y: 1.95, w: 6.0, h: 4.4, align: "left", valign: "top", isTextBox: true, margin: 0 });
s.addText("Describe it once. DevCycle AI designs, builds, tests, validates and documents — privately, on your hardware.", { x: 0.6, y: 6.35, w: 12.1, h: 0.5, fontFace: HEAD, fontSize: 14, italic: true, bold: true, color: P.blue, isTextBox: true, margin: 0 });
note(s, "One-slide recap of the whole solution, framed as bullet points, with the core value proposition and roadmap.");

pres.writeFile({ fileName: "DevCycle_AI_Overview.pptx" }).then((f) => console.log("WROTE", f));
