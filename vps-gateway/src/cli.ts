#!/usr/bin/env node

import { copyFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

type Dict = Record<string, string | undefined>;

type CliContext = {
  projectRoot: string;
};

function main(argv: string[]): void {
  const context: CliContext = {
    projectRoot: resolve(dirname(fileURLToPath(import.meta.url)), ".."),
  };

  const [command, ...rest] = argv;
  if (!command || command === "help" || command === "--help" || command === "-h") {
    printHelp();
    return;
  }

  switch (command) {
    case "build":
    case "check":
    case "dev":
    case "start": {
      runNpmScript(command, context);
      return;
    }
    case "test": {
      handleTest(rest, context);
      return;
    }
    case "smoke": {
      handleSmoke(rest, context);
      return;
    }
    case "doctor": {
      handleDoctor(rest, context);
      return;
    }
    case "service": {
      handleService(rest, context);
      return;
    }
    default: {
      die(`unknown command: ${command}`);
    }
  }
}

function handleTest(args: string[], context: CliContext): void {
  const mode = args[0] ?? "all";
  if (mode === "all") {
    runNpmScript("test", context);
    return;
  }
  if (mode === "smoke") {
    runNpmScript("test:smoke", context);
    return;
  }
  if (mode === "quick") {
    runNpmScript("test:quick", context);
    return;
  }

  die(`unknown test mode: ${mode}`);
}

function handleSmoke(args: string[], context: CliContext): void {
  const mode = args[0] ?? "live";
  if (mode !== "live") {
    die(`unknown smoke mode: ${mode}`);
  }

  const { flags } = parseFlags(args.slice(1));
  const env: Dict = {};

  if (flags["base-url"]) env.BASE_URL = flags["base-url"];
  if (flags.secret) env.ASTERISK_SHARED_SECRET = flags.secret;
  if (flags["strict-egress"] === "1" || flags["strict-egress"] === "true") {
    env.STRICT_EGRESS = "1";
  }

  runNodeScript("scripts/smoke-live.mjs", context, env);
}

function handleDoctor(args: string[], context: CliContext): void {
  const mode = args[0] ?? "deploy";
  if (mode !== "deploy") {
    die(`unknown doctor mode: ${mode}`);
  }

  runNodeScript("scripts/deploy-preflight.mjs", context);
}

function handleService(args: string[], context: CliContext): void {
  const action = args[0] ?? "help";

  if (action === "help") {
    printServiceHelp();
    return;
  }

  if (action === "print-unit") {
    const unitPath = resolve(context.projectRoot, "deploy/systemd/levi-vps-gateway.service");
    process.stdout.write(readFileSync(unitPath, "utf8"));
    return;
  }

  if (action === "install-unit") {
    const { flags } = parseFlags(args.slice(1));
    const output =
      flags.output ?? "/etc/systemd/system/levi-vps-gateway.service";
    const source = resolve(context.projectRoot, "deploy/systemd/levi-vps-gateway.service");

    mkdirSync(dirname(output), { recursive: true });
    copyFileSync(source, output);
    process.stdout.write(`[levi] installed unit -> ${output}\n`);
    return;
  }

  if (action === "reload") {
    runCommand("systemctl", ["daemon-reload"]);
    return;
  }

  if (action === "enable") {
    runCommand("systemctl", ["enable", "--now", "levi-vps-gateway.service"]);
    return;
  }

  if (action === "restart") {
    runCommand("systemctl", ["restart", "levi-vps-gateway.service"]);
    return;
  }

  if (action === "status") {
    runCommand("systemctl", ["status", "--no-pager", "levi-vps-gateway.service"]);
    return;
  }

  if (action === "logs") {
    const { flags } = parseFlags(args.slice(1));
    const lines = flags.lines ?? "200";
    runCommand("journalctl", ["-u", "levi-vps-gateway.service", "-n", lines, "--no-pager"]);
    return;
  }

  die(`unknown service action: ${action}`);
}

function parseFlags(args: string[]): { flags: Record<string, string>; extras: string[] } {
  const flags: Record<string, string> = {};
  const extras: string[] = [];

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (!arg.startsWith("--")) {
      extras.push(arg);
      continue;
    }

    const [key, maybeValue] = arg.slice(2).split("=", 2);
    if (maybeValue !== undefined) {
      flags[key] = maybeValue;
      continue;
    }

    const next = args[i + 1];
    if (next && !next.startsWith("--")) {
      flags[key] = next;
      i += 1;
    } else {
      flags[key] = "1";
    }
  }

  return { flags, extras };
}

function runNpmScript(script: string, context: CliContext): void {
  runCommand("npm", ["run", script], { cwd: context.projectRoot });
}

function runNodeScript(scriptRelativePath: string, context: CliContext, env: Dict = {}): void {
  runCommand("node", [resolve(context.projectRoot, scriptRelativePath)], {
    cwd: context.projectRoot,
    env: { ...process.env, ...env },
  });
}

function runCommand(
  command: string,
  args: string[],
  opts: { cwd?: string; env?: NodeJS.ProcessEnv } = {},
): void {
  const result = spawnSync(command, args, {
    cwd: opts.cwd,
    env: opts.env,
    stdio: "inherit",
  });

  if (result.error) {
    die(`failed to run ${command}: ${result.error.message}`);
  }

  process.exit(result.status ?? 1);
}

function die(message: string): never {
  process.stderr.write(`[levi] ${message}\n`);
  process.stderr.write("[levi] run `levi help` for usage\n");
  process.exit(1);
}

function printHelp(): void {
  process.stdout.write(`levi: VPS gateway operator CLI\n\n`);
  process.stdout.write(`Usage:\n`);
  process.stdout.write(`  levi build|check|dev|start\n`);
  process.stdout.write(`  levi test [all|smoke|quick]\n`);
  process.stdout.write(`  levi smoke live [--base-url URL] [--secret SECRET] [--strict-egress]\n`);
  process.stdout.write(`  levi doctor deploy\n`);
  process.stdout.write(`  levi service <action>\n\n`);
  printServiceHelp();
}

function printServiceHelp(): void {
  process.stdout.write(`Service actions:\n`);
  process.stdout.write(`  levi service print-unit\n`);
  process.stdout.write(`  levi service install-unit [--output PATH]\n`);
  process.stdout.write(`  levi service reload\n`);
  process.stdout.write(`  levi service enable\n`);
  process.stdout.write(`  levi service restart\n`);
  process.stdout.write(`  levi service status\n`);
  process.stdout.write(`  levi service logs [--lines N]\n`);
}

main(process.argv.slice(2));
