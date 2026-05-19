#!/usr/bin/env node
/**
 * plugify — Claude Code marketplace bootstrapper for chanshin0/Plugify.
 *
 * Writes extraKnownMarketplaces (always) and enabledPlugins (for `install` subcommand)
 * to .claude/settings.json so Claude Code picks up the marketplace + plugins
 * automatically on next start.
 */
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  existsSync,
  realpathSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";

const MARKETPLACE_KEY = "plugify";
const MARKETPLACE_REPO = "chanshin0/Plugify";

const c = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  dim: "\x1b[2m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  red: "\x1b[31m",
};

function log(msg) {
  process.stdout.write(msg + "\n");
}

function fail(msg) {
  process.stderr.write(`${c.red}✗${c.reset} ${msg}\n`);
  process.exit(1);
}

function checkNode() {
  const major = Number(process.versions.node.split(".")[0]);
  if (major < 18) {
    fail(`Node.js 18+ required. Current: ${process.versions.node}`);
  }
}

function parseArgs(argv) {
  const args = {
    global: false,
    help: false,
    uninstall: false,
    install: null,
  };
  const rest = argv.slice(2);
  for (let i = 0; i < rest.length; i++) {
    const a = rest[i];
    if (a === "--global" || a === "-g") args.global = true;
    else if (a === "--help" || a === "-h") args.help = true;
    else if (a === "--uninstall") args.uninstall = true;
    else if (a === "install") {
      const next = rest[i + 1];
      if (!next || next.startsWith("-")) {
        fail(`'install' requires a plugin name. Example: npx plugify install scenario-first`);
      }
      args.install = next;
      i++;
    } else fail(`Unknown argument: ${a}`);
  }
  return args;
}

function printHelp() {
  log(`${c.bold}plugify${c.reset} — Claude Code marketplace bootstrapper`);
  log("");
  log(`${c.bold}Usage${c.reset}`);
  log(`  npx plugify                          ${c.dim}# register marketplace only (project scope)${c.reset}`);
  log(`  npx plugify install <plugin>         ${c.dim}# register + enable a plugin${c.reset}`);
  log(`  npx plugify install <plugin> -g      ${c.dim}# user-global scope${c.reset}`);
  log(`  npx plugify --uninstall              ${c.dim}# remove marketplace entry${c.reset}`);
  log(`  npx plugify --help`);
  log("");
  log(`${c.bold}Project mode${c.reset} ${c.dim}(default)${c.reset}`);
  log(`  Writes to <cwd>/.claude/settings.json — commit it to share.`);
  log("");
  log(`${c.bold}Global mode${c.reset}`);
  log(`  Writes to ~/.claude/settings.json — applies to all projects on this machine.`);
  log("");
  log(`${c.bold}Examples${c.reset}`);
  log(`  ${c.cyan}npx plugify install scenario-first${c.reset}        ${c.dim}# project: register + enable scenario-first${c.reset}`);
  log(`  ${c.cyan}npx plugify install scenario-first -g${c.reset}     ${c.dim}# global: same, for all projects${c.reset}`);
  log("");
  log(`${c.bold}Available plugins${c.reset} ${c.dim}(see https://github.com/${MARKETPLACE_REPO})${c.reset}`);
  log(`  ${c.cyan}scenario-first${c.reset}  ${c.dim}— Job Story → GWT 자동 게이트 5단계 파이프라인${c.reset}`);
}

function readSettings(path) {
  if (!existsSync(path)) return {};
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (e) {
    fail(`Failed to parse ${path}: ${e.message}`);
  }
}

function writeSettings(path, settings) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(settings, null, 2) + "\n");
}

function mergeMarketplace(settings) {
  const existing =
    settings.extraKnownMarketplaces &&
    typeof settings.extraKnownMarketplaces === "object" &&
    !Array.isArray(settings.extraKnownMarketplaces)
      ? { ...settings.extraKnownMarketplaces }
      : {};

  const current = existing[MARKETPLACE_KEY];
  const desired = {
    source: { source: "github", repo: MARKETPLACE_REPO },
  };

  const alreadyCorrect =
    current &&
    current.source?.source === desired.source.source &&
    current.source?.repo === desired.source.repo;

  if (alreadyCorrect) {
    return { settings, added: false };
  }

  return {
    settings: {
      ...settings,
      extraKnownMarketplaces: { ...existing, [MARKETPLACE_KEY]: desired },
    },
    added: true,
  };
}

function mergePlugin(settings, pluginName) {
  const key = `${pluginName}@${MARKETPLACE_KEY}`;
  const existing =
    settings.enabledPlugins &&
    typeof settings.enabledPlugins === "object" &&
    !Array.isArray(settings.enabledPlugins)
      ? { ...settings.enabledPlugins }
      : {};

  if (existing[key] === true) {
    return { settings, added: false, key };
  }

  return {
    settings: {
      ...settings,
      enabledPlugins: { ...existing, [key]: true },
    },
    added: true,
    key,
  };
}

function unmergeMarketplace(settings) {
  const existing =
    settings.extraKnownMarketplaces &&
    typeof settings.extraKnownMarketplaces === "object" &&
    !Array.isArray(settings.extraKnownMarketplaces)
      ? { ...settings.extraKnownMarketplaces }
      : null;

  if (!existing || !(MARKETPLACE_KEY in existing)) {
    return { settings, removed: false };
  }

  delete existing[MARKETPLACE_KEY];
  const next = { ...settings };
  if (Object.keys(existing).length === 0) {
    delete next.extraKnownMarketplaces;
  } else {
    next.extraKnownMarketplaces = existing;
  }
  return { settings: next, removed: true };
}

function resolveSettingsPath(useGlobal) {
  return useGlobal
    ? join(homedir(), ".claude", "settings.json")
    : resolve(process.cwd(), ".claude", "settings.json");
}

function canonical(p) {
  try {
    return realpathSync(p);
  } catch {
    return resolve(p);
  }
}

function guardProjectMode(useGlobal) {
  if (useGlobal) return;
  if (canonical(process.cwd()) === canonical(homedir())) {
    fail(
      `cwd is your home directory (${homedir()}).\n` +
        `  Project mode would write to ~/.claude/settings.json — same as --global.\n` +
        `  → cd into a project first, or pass --global if that's what you want.`
    );
  }
}

function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    printHelp();
    return;
  }

  checkNode();
  guardProjectMode(args.global);

  const settingsPath = resolveSettingsPath(args.global);
  const scopeLabel = args.global ? "user-global" : "project";

  const modeLabel = args.uninstall
    ? "uninstall"
    : args.install
    ? `install ${args.install}`
    : "register marketplace";

  log(`${c.bold}plugify ${modeLabel}${c.reset} ${c.dim}(${scopeLabel} scope)${c.reset}`);
  log(`${c.dim}Target: ${settingsPath}${c.reset}\n`);

  const current = readSettings(settingsPath);

  if (args.uninstall) {
    const { settings, removed } = unmergeMarketplace(current);
    if (removed) {
      writeSettings(settingsPath, settings);
      log(`${c.green}✓${c.reset} Removed "${MARKETPLACE_KEY}" from extraKnownMarketplaces`);
    } else {
      log(`${c.yellow}•${c.reset} "${MARKETPLACE_KEY}" not registered — nothing to do`);
    }
    log("");
    log(`${c.bold}Cleanup complete.${c.reset} ${c.dim}To also remove installed plugins:${c.reset}`);
    log(`  ${c.cyan}claude plugin uninstall <plugin>@${MARKETPLACE_KEY}${c.reset}`);
    return;
  }

  // Step 1: marketplace
  const mp = mergeMarketplace(current);
  let next = mp.settings;
  if (mp.added) {
    log(`${c.green}✓${c.reset} Registered "${MARKETPLACE_KEY}" → ${MARKETPLACE_REPO}`);
  } else {
    log(`${c.yellow}•${c.reset} "${MARKETPLACE_KEY}" already registered`);
  }

  // Step 2: plugin (if install subcommand)
  let pluginKey = null;
  if (args.install) {
    const pl = mergePlugin(next, args.install);
    next = pl.settings;
    pluginKey = pl.key;
    if (pl.added) {
      log(`${c.green}✓${c.reset} Enabled "${pl.key}"`);
    } else {
      log(`${c.yellow}•${c.reset} "${pl.key}" already enabled`);
    }
  }

  if (mp.added || (args.install && pluginKey && next.enabledPlugins?.[pluginKey])) {
    writeSettings(settingsPath, next);
  }

  log("");
  if (!args.global) {
    log(`${c.bold}Share with team?${c.reset} ${c.dim}(commit to share with future cloners)${c.reset}`);
    log(`  ${c.cyan}git add .claude/settings.json && git commit -m "chore: register plugify"${c.reset}`);
    log("");
  }
  log(`${c.bold}Next${c.reset}`);
  if (args.install) {
    log(`  ${c.cyan}1.${c.reset} Restart Claude Code (or run /reload-plugins)`);
    log(`  ${c.cyan}2.${c.reset} Claude Code prompts: trust marketplace + install plugin`);
    log(`  ${c.cyan}3.${c.reset} ${args.install}@${MARKETPLACE_KEY} is ready to use`);
  } else {
    log(`  Use ${c.cyan}claude plugin install <plugin>@${MARKETPLACE_KEY}${c.reset} inside Claude Code,`);
    log(`  or re-run ${c.cyan}npx plugify install <plugin>${c.reset} to enable one declaratively.`);
  }
}

main();
