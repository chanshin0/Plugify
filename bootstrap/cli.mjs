#!/usr/bin/env node
/**
 * plugify — one-shot installer for the chanshin0/Plugify skills + agents,
 * shared across Claude Code (~/.claude) and Codex (~/.codex) from one SSOT.
 *
 * Default (`npx plugify`):
 *   1. Locate the canonical repo at a STABLE path (reuse an existing clone —
 *      e.g. the Claude marketplace copy — or clone fresh to ~/.plugify).
 *      npx itself runs from a throwaway cache, so install.sh must NOT run from
 *      there: its symlinks would dangle the moment the cache is evicted.
 *   2. git pull (best-effort; skipped if the clone has local changes).
 *   3. Run <repo>/scripts/install.sh — symlinks skills into ~/.claude/skills
 *      and ~/.codex/skills, and generates agents (.md + .toml) for both tools.
 *
 * Opt-in (`npx plugify --register [-g]`):
 *   Also register the Claude Code marketplace in settings.json (Claude-only;
 *   not needed for Codex, not needed for the symlink/generation install above).
 */
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  existsSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const MARKETPLACE_KEY = "plugify";
const MARKETPLACE_REPO = "chanshin0/Plugify";
const REPO_URL = "https://github.com/chanshin0/Plugify.git";

const c = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  dim: "\x1b[2m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  red: "\x1b[31m",
};

const log = (m) => process.stdout.write(m + "\n");
const fail = (m) => {
  process.stderr.write(`${c.red}✗${c.reset} ${m}\n`);
  process.exit(1);
};

function checkNode() {
  const major = Number(process.versions.node.split(".")[0]);
  if (major < 18) fail(`Node.js 18+ required. Current: ${process.versions.node}`);
}

function has(bin) {
  const r = spawnSync(bin, ["--version"], { stdio: "ignore" });
  return !r.error && r.status === 0;
}

// --- repo location -------------------------------------------------------

function isRepo(p) {
  return (
    !!p &&
    existsSync(join(p, ".git")) &&
    existsSync(join(p, "scripts", "install.sh"))
  );
}

// Reuse an existing clone if we can find one (avoids a second copy that would
// split the SSOT). Otherwise install fresh to ~/.plugify.
function resolveStableRepo() {
  const candidates = [
    process.env.PLUGIFY_HOME,
    join(homedir(), ".claude", "plugins", "marketplaces", "plugify"),
    join(homedir(), ".plugify"),
  ];
  for (const p of candidates) {
    if (isRepo(p)) return { path: p, existed: true };
  }
  return { path: join(homedir(), ".plugify"), existed: false };
}

function gitClone(dest) {
  log(`${c.dim}git clone ${REPO_URL} ${dest}${c.reset}`);
  const r = spawnSync("git", ["clone", "--depth", "1", REPO_URL, dest], {
    stdio: "inherit",
  });
  if (r.status !== 0) fail(`git clone failed (status ${r.status})`);
}

function gitPullIfClean(repo) {
  const dirty = spawnSync("git", ["-C", repo, "status", "--porcelain"], {
    encoding: "utf8",
  });
  if (dirty.status === 0 && dirty.stdout.trim()) {
    log(`${c.yellow}•${c.reset} 로컬 변경 있음 → pull 건너뜀 (현재 상태로 설치): ${repo}`);
    return;
  }
  const r = spawnSync("git", ["-C", repo, "pull", "--ff-only"], { stdio: "inherit" });
  if (r.status !== 0) {
    log(`${c.yellow}•${c.reset} git pull 실패 → 기존 클론 그대로 설치 진행`);
  }
}

function runInstall(repo) {
  const script = join(repo, "scripts", "install.sh");
  if (!existsSync(script)) fail(`install script not found: ${script}`);
  log(`${c.dim}bash ${script}${c.reset}\n`);
  const r = spawnSync("bash", [script], { stdio: "inherit" });
  if (r.status !== 0) fail(`install.sh exited with status ${r.status}`);
}

function setup() {
  if (!has("git")) fail("git 이 필요합니다 (PATH 에 없음).");
  const { path: repo, existed } = resolveStableRepo();

  log(`${c.bold}plugify setup${c.reset}`);
  log(`${c.dim}stable repo: ${repo}${existed ? " (기존 클론 재사용)" : " (신규 clone)"}${c.reset}\n`);

  if (existed) gitPullIfClean(repo);
  else {
    mkdirSync(dirname(repo), { recursive: true });
    gitClone(repo);
  }

  runInstall(repo);

  log("");
  log(`${c.green}✓${c.reset} plugify 설치 완료 — 스킬·에이전트가 Claude(~/.claude) + Codex(~/.codex) 양쪽에 노출됨.`);
  log(`${c.dim}⚠ Claude/Codex 세션을 재시작해야 agentType 레지스트리에 반영됩니다.${c.reset}`);
  log(`${c.dim}  (SessionStart: 관리된 3-repo workspace는 안전 최신화, 단일 repo는 로컬 agent self-heal)${c.reset}`);
}

// --- Claude marketplace registration (opt-in) ----------------------------

function readSettings(path) {
  if (!existsSync(path)) return {};
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (e) {
    fail(`Failed to parse ${path}: ${e.message}`);
  }
}

function registerMarketplace(useGlobal) {
  const path = useGlobal
    ? join(homedir(), ".claude", "settings.json")
    : resolve(process.cwd(), ".claude", "settings.json");
  const s = readSettings(path);
  const existing =
    s.extraKnownMarketplaces && typeof s.extraKnownMarketplaces === "object" && !Array.isArray(s.extraKnownMarketplaces)
      ? { ...s.extraKnownMarketplaces }
      : {};
  const cur = existing[MARKETPLACE_KEY];
  const ok = cur && cur.source?.source === "github" && cur.source?.repo === MARKETPLACE_REPO;
  if (ok) {
    log(`${c.yellow}•${c.reset} "${MARKETPLACE_KEY}" already registered → ${path}`);
    return;
  }
  existing[MARKETPLACE_KEY] = { source: { source: "github", repo: MARKETPLACE_REPO } };
  const next = { ...s, extraKnownMarketplaces: existing };
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(next, null, 2) + "\n");
  log(`${c.green}✓${c.reset} Registered "${MARKETPLACE_KEY}" → ${MARKETPLACE_REPO} (${path})`);
}

// --- args / help ---------------------------------------------------------

function printHelp() {
  log(`${c.bold}plugify${c.reset} — Claude Code + Codex 공용 스킬/에이전트 설치기`);
  log("");
  log(`${c.bold}Usage${c.reset}`);
  log(`  npx plugify                  ${c.dim}# 정본 clone/locate → install.sh (claude+codex 셋업)${c.reset}`);
  log(`  npx plugify --register       ${c.dim}# (추가) Claude 마켓플레이스 등록 — project scope${c.reset}`);
  log(`  npx plugify --register -g    ${c.dim}# (추가) Claude 마켓플레이스 등록 — user-global${c.reset}`);
  log(`  npx plugify --help`);
  log("");
  log(`${c.bold}Env${c.reset}`);
  log(`  PLUGIFY_HOME   ${c.dim}# 정본 레포 경로 강제 (기본: 기존 클론 자동탐지 → 없으면 ~/.plugify)${c.reset}`);
}

function main() {
  checkNode();
  const argv = process.argv.slice(2);
  const want = { help: false, register: false, global: false };
  for (const a of argv) {
    if (a === "--help" || a === "-h") want.help = true;
    else if (a === "--register") want.register = true;
    else if (a === "--global" || a === "-g") want.global = true;
    else fail(`Unknown argument: ${a} (try --help)`);
  }

  if (want.help) return printHelp();

  setup();
  if (want.register) {
    log("");
    registerMarketplace(want.global);
  }
}

main();
