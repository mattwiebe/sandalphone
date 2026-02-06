#!/usr/bin/env node

import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { createInterface } from "node:readline/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { applyEnvUpdates, parseEnvFile, type EnvMap } from "./cli-env-file.js";

type Dict = Record<string, string | undefined>;

type CliContext = {
  projectRoot: string;
};

type PromptOptions = {
  defaultValue?: string;
  required?: boolean;
  secret?: boolean;
  validate?: (value: string) => string | undefined;
};

async function main(argv: string[]): Promise<void> {
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
    case "install": {
      await handleInstall(rest, context);
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

async function handleInstall(args: string[], context: CliContext): Promise<void> {
  const { flags } = parseFlags(args);
  const examplePath = resolve(context.projectRoot, ".env.example");
  const envPath = resolve(context.projectRoot, flags["env-path"] ?? flags["env-file"] ?? ".env");

  if (!existsSync(examplePath)) {
    die(`missing template file: ${examplePath}`);
  }

  const templateText = readFileSync(examplePath, "utf8");
  const currentText = existsSync(envPath) ? readFileSync(envPath, "utf8") : templateText;
  const currentValues = parseEnvFile(currentText);

  process.stdout.write(`[sandalphone] interactive install\n`);
  process.stdout.write(`[sandalphone] target env file: ${envPath}\n`);
  process.stdout.write(`[sandalphone] press Enter to keep shown default\n\n`);

  const rl = createInterface({ input: process.stdin, output: process.stdout });

  try {
    const defaults: EnvMap = {
      PORT: currentValues.PORT ?? "8080",
      PUBLIC_BASE_URL: currentValues.PUBLIC_BASE_URL ?? "",
      DESTINATION_PHONE_E164: currentValues.DESTINATION_PHONE_E164 ?? "+15555550100",
      TWILIO_PHONE_NUMBER: currentValues.TWILIO_PHONE_NUMBER ?? "",
      VOIPMS_DID: currentValues.VOIPMS_DID ?? "",
      ASTERISK_SHARED_SECRET:
        currentValues.ASTERISK_SHARED_SECRET ?? randomBytes(16).toString("hex"),
      TWILIO_AUTH_TOKEN: currentValues.TWILIO_AUTH_TOKEN ?? "",
      ASSEMBLYAI_API_KEY: currentValues.ASSEMBLYAI_API_KEY ?? "",
      GOOGLE_TRANSLATE_API_KEY: currentValues.GOOGLE_TRANSLATE_API_KEY ?? "",
      AWS_ACCESS_KEY_ID: currentValues.AWS_ACCESS_KEY_ID ?? "",
      AWS_SECRET_ACCESS_KEY: currentValues.AWS_SECRET_ACCESS_KEY ?? "",
      AWS_REGION: currentValues.AWS_REGION ?? "us-west-2",
      POLLY_VOICE_EN: currentValues.POLLY_VOICE_EN ?? "Joanna",
      POLLY_VOICE_ES: currentValues.POLLY_VOICE_ES ?? "Lupe",
    };

    const updates: EnvMap = {
      PORT: await prompt(rl, "Gateway HTTP port", {
        defaultValue: defaults.PORT,
        required: true,
        validate: (value) => {
          const port = Number(value);
          if (!Number.isFinite(port) || port <= 0) return "must be a positive number";
          return undefined;
        },
      }),
      PUBLIC_BASE_URL: await prompt(rl, "Public base URL (for Twilio signature checks)", {
        defaultValue: defaults.PUBLIC_BASE_URL,
      }),
      DESTINATION_PHONE_E164: await prompt(rl, "Primary destination phone (E.164)", {
        defaultValue: defaults.DESTINATION_PHONE_E164,
        required: true,
        validate: (value) => {
          if (!/^\+[1-9]\d{7,14}$/.test(value)) {
            return "must be E.164 format like +15555550100";
          }
          return undefined;
        },
      }),
      TWILIO_PHONE_NUMBER: await prompt(rl, "Twilio DID number (optional)", {
        defaultValue: defaults.TWILIO_PHONE_NUMBER,
      }),
      VOIPMS_DID: await prompt(rl, "VoIP.ms DID number (optional)", {
        defaultValue: defaults.VOIPMS_DID,
      }),
      ASTERISK_SHARED_SECRET: await prompt(rl, "Asterisk shared secret", {
        defaultValue: defaults.ASTERISK_SHARED_SECRET,
        secret: true,
        required: true,
      }),
      TWILIO_AUTH_TOKEN: await prompt(rl, "Twilio auth token", {
        defaultValue: defaults.TWILIO_AUTH_TOKEN,
        secret: true,
      }),
      ASSEMBLYAI_API_KEY: await prompt(rl, "AssemblyAI API key", {
        defaultValue: defaults.ASSEMBLYAI_API_KEY,
        secret: true,
      }),
      GOOGLE_TRANSLATE_API_KEY: await prompt(rl, "Google Translate API key", {
        defaultValue: defaults.GOOGLE_TRANSLATE_API_KEY,
        secret: true,
      }),
      AWS_ACCESS_KEY_ID: await prompt(rl, "AWS access key ID", {
        defaultValue: defaults.AWS_ACCESS_KEY_ID,
        secret: true,
      }),
      AWS_SECRET_ACCESS_KEY: await prompt(rl, "AWS secret access key", {
        defaultValue: defaults.AWS_SECRET_ACCESS_KEY,
        secret: true,
      }),
      AWS_REGION: await prompt(rl, "AWS region", {
        defaultValue: defaults.AWS_REGION,
        required: true,
      }),
      POLLY_VOICE_EN: await prompt(rl, "Polly English voice", {
        defaultValue: defaults.POLLY_VOICE_EN,
        required: true,
      }),
      POLLY_VOICE_ES: await prompt(rl, "Polly Spanish voice", {
        defaultValue: defaults.POLLY_VOICE_ES,
        required: true,
      }),
    };

    const mergedText = applyEnvUpdates(currentText, updates);
    writeFileSync(envPath, mergedText.endsWith("\n") ? mergedText : `${mergedText}\n`, "utf8");

    process.stdout.write(`\n[sandalphone] wrote env file: ${envPath}\n`);
    process.stdout.write("[sandalphone] next steps:\n");
    process.stdout.write("  1. sandalphone doctor deploy\n");

    if (!updates.PUBLIC_BASE_URL) {
      process.stdout.write("  2. Expose local service with a public HTTPS tunnel (Twilio cannot reach private IP:port)\n");
      process.stdout.write("     Example with Tailscale Funnel:\n");
      process.stdout.write("       tailscale funnel 8080\n");
      process.stdout.write("       # then set PUBLIC_BASE_URL in .env to the shown https://... URL\n");
    }

    const publicBaseUrl = updates.PUBLIC_BASE_URL || "https://<your-public-funnel-domain>";
    process.stdout.write("  3. Configure Twilio:\n");
    process.stdout.write(`     - Voice webhook: ${publicBaseUrl}/twilio/voice\n`);
    process.stdout.write(`     - Media stream WS: wss://${stripScheme(publicBaseUrl)}/twilio/stream\n`);
    process.stdout.write("  4. Start service locally and run smoke:\n");
    process.stdout.write("     - sandalphone start\n");
    process.stdout.write(`     - sandalphone smoke live --base-url ${publicBaseUrl}\n`);
  } finally {
    rl.close();
  }
}

function stripScheme(url: string): string {
  return url.replace(/^https?:\/\//, "");
}

async function prompt(
  rl: ReturnType<typeof createInterface>,
  label: string,
  opts: PromptOptions,
): Promise<string> {
  while (true) {
    const renderedDefault =
      opts.defaultValue !== undefined
        ? opts.secret
          ? opts.defaultValue
            ? " [set]"
            : " [empty]"
          : ` [${opts.defaultValue}]`
        : "";

    let raw: string;
    try {
      raw = await rl.question(`${label}${renderedDefault}: `);
    } catch {
      if (opts.defaultValue !== undefined) return opts.defaultValue;
      if (opts.required) {
        throw new Error(`missing required input for ${label}`);
      }
      return "";
    }
    const value = raw.trim() === "" ? opts.defaultValue ?? "" : raw.trim();

    if (opts.required && value.length === 0) {
      process.stdout.write("  value is required\n");
      continue;
    }

    const error = opts.validate?.(value);
    if (error) {
      process.stdout.write(`  ${error}\n`);
      continue;
    }

    return value;
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
    const unitPath = resolve(context.projectRoot, "deploy/systemd/sandalphone-vps-gateway.service");
    process.stdout.write(readFileSync(unitPath, "utf8"));
    return;
  }

  if (action === "install-unit") {
    const { flags } = parseFlags(args.slice(1));
    const output =
      flags.output ?? "/etc/systemd/system/sandalphone-vps-gateway.service";
    const source = resolve(context.projectRoot, "deploy/systemd/sandalphone-vps-gateway.service");

    mkdirSync(dirname(output), { recursive: true });
    copyFileSync(source, output);
    process.stdout.write(`[sandalphone] installed unit -> ${output}\n`);
    return;
  }

  if (action === "reload") {
    runCommand("systemctl", ["daemon-reload"]);
    return;
  }

  if (action === "enable") {
    runCommand("systemctl", ["enable", "--now", "sandalphone-vps-gateway.service"]);
    return;
  }

  if (action === "restart") {
    runCommand("systemctl", ["restart", "sandalphone-vps-gateway.service"]);
    return;
  }

  if (action === "status") {
    runCommand("systemctl", ["status", "--no-pager", "sandalphone-vps-gateway.service"]);
    return;
  }

  if (action === "logs") {
    const { flags } = parseFlags(args.slice(1));
    const lines = flags.lines ?? "200";
    runCommand("journalctl", ["-u", "sandalphone-vps-gateway.service", "-n", lines, "--no-pager"]);
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
  process.stderr.write(`[sandalphone] ${message}\n`);
  process.stderr.write("[sandalphone] run `sandalphone help` for usage\n");
  process.exit(1);
}

function printHelp(): void {
  process.stdout.write(`sandalphone: VPS gateway operator CLI\n\n`);
  process.stdout.write(`Usage:\n`);
  process.stdout.write(`  sandalphone install [--env-path PATH]\n`);
  process.stdout.write(`  sandalphone build|check|dev|start\n`);
  process.stdout.write(`  sandalphone test [all|smoke|quick]\n`);
  process.stdout.write(`  sandalphone smoke live [--base-url URL] [--secret SECRET] [--strict-egress]\n`);
  process.stdout.write(`  sandalphone doctor deploy\n`);
  process.stdout.write(`  sandalphone service <action>\n\n`);
  process.stdout.write(`Legacy alias: levi <command>\n\n`);
  printServiceHelp();
}

function printServiceHelp(): void {
  process.stdout.write(`Service actions:\n`);
  process.stdout.write(`  sandalphone service print-unit\n`);
  process.stdout.write(`  sandalphone service install-unit [--output PATH]\n`);
  process.stdout.write(`  sandalphone service reload\n`);
  process.stdout.write(`  sandalphone service enable\n`);
  process.stdout.write(`  sandalphone service restart\n`);
  process.stdout.write(`  sandalphone service status\n`);
  process.stdout.write(`  sandalphone service logs [--lines N]\n`);
}

void main(process.argv.slice(2)).catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  die(message);
});
