#!/usr/bin/env node

import {
  copyFileSync,
  createReadStream,
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { createInterface } from "node:readline/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir, platform } from "node:os";
import { applyEnvUpdates, parseEnvFile, removeEnvKeys, type EnvMap } from "./cli-env-file.js";
import { extractFunnelUrl, extractFunnelUrlFromText } from "./cli-funnel.js";

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

type CommandResult = {
  status: number;
  stdout: string;
  stderr: string;
  error?: Error;
  timedOut?: boolean;
};

function pickNonEmpty(...values: Array<string | undefined>): string | undefined {
  for (const value of values) {
    if (value && value.trim().length > 0) return value;
  }
  return undefined;
}

async function main(argv: string[]): Promise<void> {
  const context: CliContext = {
    projectRoot: resolve(dirname(fileURLToPath(import.meta.url)), ".."),
  };

  const [command, ...rest] = argv;
  if (command === "--version" || command === "-v" || command === "version") {
    process.stdout.write(`${cliVersion()}\n`);
    return;
  }
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
    case "urls": {
      handleUrls(rest, context);
      return;
    }
    case "openclaw": {
      await handleOpenClaw(rest, context);
      return;
    }
    case "session": {
      await handleSession(rest, context);
      return;
    }
    case "service": {
      handleService(rest, context);
      return;
    }
    case "funnel": {
      handleFunnel(rest, context);
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
  const envExists = existsSync(envPath);
  const currentText = envExists ? readFileSync(envPath, "utf8") : templateText;
  const currentValues = parseEnvFile(currentText);

  const ttyPath = "/dev/tty";
  const hasTty = process.stdin.isTTY || existsSync(ttyPath);
  if (!hasTty) {
    die("interactive install requires a TTY (run it in a real terminal, not a background pipe)");
  }

  process.stdout.write(`[sandalphone] interactive install\n`);
  process.stdout.write(`[sandalphone] target env file: ${envPath}\n`);
  if (envExists) {
    process.stdout.write("[sandalphone] loaded existing values from env file\n");
  }
  process.stdout.write(`[sandalphone] press Enter to keep shown default\n\n`);

  const rl = createInterface({
    input: process.stdin.isTTY ? process.stdin : createReadStream(ttyPath),
    output: process.stdout,
  });

  try {
    const defaults: EnvMap = {
      PORT: currentValues.PORT ?? "8080",
      PUBLIC_BASE_URL: currentValues.PUBLIC_BASE_URL ?? "",
      OUTBOUND_TARGET_E164:
        currentValues.OUTBOUND_TARGET_E164 ??
        currentValues.DESTINATION_PHONE_E164 ??
        "+15555550100",
      TWILIO_PHONE_NUMBER: currentValues.TWILIO_PHONE_NUMBER ?? "",
      VOIPMS_DID: currentValues.VOIPMS_DID ?? "",
      ASTERISK_SHARED_SECRET:
        pickNonEmpty(currentValues.ASTERISK_SHARED_SECRET) ?? randomBytes(16).toString("hex"),
      CONTROL_API_SECRET:
        pickNonEmpty(currentValues.CONTROL_API_SECRET) ?? randomBytes(16).toString("hex"),
      TWILIO_AUTH_TOKEN: currentValues.TWILIO_AUTH_TOKEN ?? "",
      GOOGLE_CLOUD_API_KEY:
        currentValues.GOOGLE_CLOUD_API_KEY ??
        currentValues.GOOGLE_TTS_API_KEY ??
        currentValues.GOOGLE_TRANSLATE_API_KEY ??
        "",
      GOOGLE_TTS_VOICE_EN: currentValues.GOOGLE_TTS_VOICE_EN ?? "en-US-Standard-C",
      GOOGLE_TTS_VOICE_ES: currentValues.GOOGLE_TTS_VOICE_ES ?? "es-US-Standard-A",
      OPENCLAW_BRIDGE_URL: currentValues.OPENCLAW_BRIDGE_URL ?? "",
      OPENCLAW_BRIDGE_API_KEY: currentValues.OPENCLAW_BRIDGE_API_KEY ?? "",
      OPENCLAW_BRIDGE_TIMEOUT_MS: currentValues.OPENCLAW_BRIDGE_TIMEOUT_MS ?? "1200",
    };

    const updates: EnvMap = {};
    const persist = (key: string, value: string): string => {
      updates[key] = value;
      updateEnvFile(envPath, { [key]: value }, context.projectRoot);
      return value;
    };
    const promptAndPersist = async (
      key: string,
      label: string,
      opts: PromptOptions,
    ): Promise<string> => {
      const value = await prompt(rl, label, opts);
      return persist(key, value);
    };
    const promptWithHelpAndPersist = async (
      key: string,
      label: string,
      defaultValue: string | undefined,
      helpLines: string[],
    ): Promise<string> => {
      const value = await promptWithHelp(rl, label, defaultValue, helpLines);
      return persist(key, value);
    };

    const selectedPort = await promptAndPersist("PORT", "Gateway HTTP port", {
      defaultValue: defaults.PORT,
      required: true,
      validate: (value) => {
        const port = Number(value);
        if (!Number.isFinite(port) || port <= 0) return "must be a positive number";
        return undefined;
      },
    });

    let detectedPublicBaseUrl = "";
    const enableFunnel = await promptYesNo(
      rl,
      "Set up Tailscale Funnel now and auto-fill PUBLIC_BASE_URL?",
      defaults.PUBLIC_BASE_URL.length === 0,
    );
    if (enableFunnel) {
      const url = setupFunnelAndPersistEnv(context, selectedPort, envPath);
      if (url) {
        detectedPublicBaseUrl = url;
        process.stdout.write(`[sandalphone] detected funnel URL: ${url}\n`);
      } else {
        process.stdout.write("[sandalphone] funnel configured but URL was not detected automatically\n");
        printManualFunnelUrlSteps(selectedPort);
      }
    }

    process.stdout.write(
      "[sandalphone] outbound bridge target = the phone number Sandalphone dials (usually your phone), not your Twilio/VoIP.ms managed DID\n",
    );

    await promptAndPersist("OUTBOUND_TARGET_E164", "Outbound bridge target phone (E.164)", {
      defaultValue: defaults.OUTBOUND_TARGET_E164,
      required: true,
      validate: (value) => {
        if (!/^\+[1-9]\d{7,14}$/.test(value)) {
          return "must be E.164 format like +15555550100";
        }
        return undefined;
      },
    });
    await promptAndPersist("PUBLIC_BASE_URL", "Public base URL (for Twilio signature checks)", {
      defaultValue: detectedPublicBaseUrl || defaults.PUBLIC_BASE_URL,
    });
    await promptAndPersist("TWILIO_PHONE_NUMBER", "Twilio DID number (optional)", {
      defaultValue: defaults.TWILIO_PHONE_NUMBER,
    });
    await promptAndPersist("VOIPMS_DID", "VoIP.ms DID number (optional)", {
      defaultValue: defaults.VOIPMS_DID,
    });
    await promptAndPersist(
      "ASTERISK_SHARED_SECRET",
      "Asterisk shared secret (press Enter to accept)",
      {
        defaultValue: defaults.ASTERISK_SHARED_SECRET,
        secret: true,
        required: true,
      },
    );
    await promptAndPersist("CONTROL_API_SECRET", "Control API secret (press Enter to accept)", {
      defaultValue: defaults.CONTROL_API_SECRET,
      secret: true,
      required: true,
    });
    await promptAndPersist(
      "TWILIO_AUTH_TOKEN",
      "Twilio auth token" +
        ((updates.TWILIO_PHONE_NUMBER ?? "").trim().length > 0 ? " (required)" : " (optional)"),
      {
        defaultValue: defaults.TWILIO_AUTH_TOKEN,
        secret: true,
        required: (updates.TWILIO_PHONE_NUMBER ?? "").trim().length > 0,
      },
    );
    await promptWithHelpAndPersist(
      "GOOGLE_CLOUD_API_KEY",
      "Google Cloud API key (Speech-to-Text + Text-to-Speech + Translate)",
      defaults.GOOGLE_CLOUD_API_KEY,
      [
        "Enable these APIs, then create a single API key:",
        "  - Cloud Speech-to-Text API",
        "  - Cloud Text-to-Speech API",
        "  - Cloud Translation API",
        "Manage API keys here:",
        "  https://console.cloud.google.com/apis/credentials",
      ],
    );

    await promptAndPersist("GOOGLE_TTS_VOICE_EN", "Google TTS voice (en)", {
      defaultValue: defaults.GOOGLE_TTS_VOICE_EN,
      required: true,
    });
    await promptAndPersist("GOOGLE_TTS_VOICE_ES", "Google TTS voice (es)", {
      defaultValue: defaults.GOOGLE_TTS_VOICE_ES,
      required: true,
    });

    await promptAndPersist("OPENCLAW_BRIDGE_URL", "OpenClaw bridge URL (optional)", {
      defaultValue: defaults.OPENCLAW_BRIDGE_URL,
    });
    await promptAndPersist("OPENCLAW_BRIDGE_API_KEY", "OpenClaw bridge API key (optional)", {
      defaultValue: defaults.OPENCLAW_BRIDGE_API_KEY,
      secret: true,
    });
    await promptAndPersist("OPENCLAW_BRIDGE_TIMEOUT_MS", "OpenClaw bridge timeout ms", {
      defaultValue: defaults.OPENCLAW_BRIDGE_TIMEOUT_MS,
      required: true,
      validate: (value) => {
        const timeout = Number(value);
        if (!Number.isFinite(timeout) || timeout < 100) return "must be a number >= 100";
        return undefined;
      },
    });

    if (!updates.TWILIO_PHONE_NUMBER && !updates.VOIPMS_DID) {
      const cont = await promptYesNo(
        rl,
        "No inbound DID configured (Twilio or VoIP.ms). Continue anyway?",
        false,
      );
      if (!cont) {
        throw new Error("install canceled: configure a DID then re-run install");
      }
    }

    if (!updates.GOOGLE_CLOUD_API_KEY) {
      const cont = await promptYesNo(
        rl,
        "Missing Google Cloud API key; STT/TTS/Translate will be disabled. Continue anyway?",
        false,
      );
      if (!cont) {
        throw new Error("install canceled: add Google Cloud API key then re-run install");
      }
    }

    updateEnvFile(envPath, updates, context.projectRoot);

    const publicBaseUrl = updates.PUBLIC_BASE_URL;

    process.stdout.write(`\n[sandalphone] wrote env file: ${envPath}\n`);
    process.stdout.write("[sandalphone] next steps:\n");
    process.stdout.write("  1. sandalphone doctor deploy\n");

    if (!publicBaseUrl) {
      process.stdout.write("  2. Expose local service with a public HTTPS tunnel (Twilio cannot reach private IP:port)\n");
      process.stdout.write("     Example with Tailscale Funnel:\n");
      process.stdout.write(`       sandalphone funnel up --port ${updates.PORT}\n`);
      process.stdout.write("       # then set PUBLIC_BASE_URL in .env to the shown https://... URL\n");
      printManualFunnelUrlSteps(updates.PORT);
    }

    const base = publicBaseUrl || "https://<your-public-funnel-domain>";
    process.stdout.write("  3. Configure Twilio:\n");
    process.stdout.write(`     - Voice webhook: ${base}/twilio/voice\n`);
    process.stdout.write(`     - Media stream WS: wss://${stripScheme(base)}/twilio/stream\n`);
    process.stdout.write("  4. Start service locally and run smoke:\n");
    process.stdout.write("     - sandalphone start\n");
    process.stdout.write(`     - sandalphone smoke live --base-url ${base}\n`);
  } finally {
    rl.close();
  }
}

function handleFunnel(args: string[], context: CliContext): void {
  const action = args[0] ?? "help";

  if (action === "help") {
    printFunnelHelp();
    return;
  }

  if (action === "up") {
    const { flags } = parseFlags(args.slice(1));
    const port = flags.port ?? "8080";
    const envPath = resolve(context.projectRoot, flags["env-path"] ?? ".env");

    const url = setupFunnelAndPersistEnv(context, port, envPath, {
      bg: flags.bg !== "0" && flags.bg !== "false",
      yes: flags.yes !== "0" && flags.yes !== "false",
    });

    if (!url) {
      die("funnel configured but could not detect public URL; run `sandalphone funnel status` and set PUBLIC_BASE_URL manually");
    }

    process.stdout.write(`[sandalphone] PUBLIC_BASE_URL updated to ${url} in ${envPath}\n`);
    process.stdout.write(`[sandalphone] Twilio voice webhook: ${url}/twilio/voice\n`);
    process.stdout.write(`[sandalphone] Twilio media stream: wss://${stripScheme(url)}/twilio/stream\n`);
    return;
  }

  if (action === "status") {
    const result = runCommandCapture("tailscale", ["funnel", "status", "--json"]);
    if (result.status !== 0) {
      process.stderr.write(result.stderr);
      die("failed to read funnel status (is tailscaled running?)");
    }

    const url = extractFunnelUrl(result.stdout);
    if (url) {
      process.stdout.write(`[sandalphone] funnel url: ${url}\n`);
    } else {
      process.stdout.write("[sandalphone] funnel active but URL not detected from status json\n");
    }

    process.stdout.write(result.stdout.endsWith("\n") ? result.stdout : `${result.stdout}\n`);
    return;
  }

  if (action === "reset" || action === "down") {
    const { flags } = parseFlags(args.slice(1));
    const result = runCommandCapture("tailscale", ["funnel", "reset"]);
    if (result.status !== 0) {
      process.stderr.write(result.stderr);
      die("failed to reset funnel");
    }
    process.stdout.write(result.stdout);

    if (flags["clear-env"] === "1" || flags["clear-env"] === "true") {
      const envPath = resolve(context.projectRoot, flags["env-path"] ?? ".env");
      updateEnvFile(envPath, { PUBLIC_BASE_URL: "" }, context.projectRoot);
      process.stdout.write(`[sandalphone] cleared PUBLIC_BASE_URL in ${envPath}\n`);
    }
    return;
  }

  die(`unknown funnel action: ${action}`);
}

function setupFunnelAndPersistEnv(
  context: CliContext,
  port: string,
  envPath: string,
  opts: { bg?: boolean; yes?: boolean } = {},
): string | undefined {
  process.stdout.write("[sandalphone] configuring Tailscale Funnel...\n");
  const args = ["funnel"];
  if (opts.bg ?? true) args.push("--bg");
  if (opts.yes ?? true) args.push("--yes");
  args.push(port);
  process.stdout.write(`[sandalphone] running: tailscale ${args.join(" ")}\n`);

  const up = runCommandCapture("tailscale", args, { timeoutMs: 15000 });
  process.stdout.write(`[sandalphone] tailscale exit status: ${up.status}\n`);
  const spawnErrorMessage = up.error?.message;
  if (spawnErrorMessage) {
    process.stderr.write(`[sandalphone] tailscale spawn error: ${spawnErrorMessage}\n`);
  }
  if (up.timedOut) {
    process.stderr.write(
      "[sandalphone] tailscale funnel timed out; run `sandalphone funnel up --port " +
        `${port}` +
        "` manually in another terminal\n",
    );
    return undefined;
  }
  if (up.status !== 0) {
    const combinedError = `${up.stdout}\n${up.stderr}`;
    if (/serve config denied|Access denied/i.test(combinedError)) {
      process.stderr.write(
        "[sandalphone] tailscale denied funnel config. On Linux, run one of:\n",
      );
      process.stderr.write("  1) sudo tailscale set --operator=$USER\n");
      process.stderr.write(`  2) sudo tailscale funnel --bg --yes ${port}\n`);
      return undefined;
    }
    const disabledUrl = extractFunnelEnableUrl(`${up.stdout}\n${up.stderr}`);
    if (disabledUrl) {
      process.stderr.write(
        "[sandalphone] Funnel is disabled for this tailnet. Enable it first:\n",
      );
      process.stderr.write(`  ${disabledUrl}\n`);
      process.stderr.write(
        "[sandalphone] After enabling, re-run `sandalphone funnel up --port " +
          `${port}` +
          "` or continue install and paste PUBLIC_BASE_URL manually.\n",
      );
      return undefined;
    }
    const failureOut = `${up.stdout}\n${up.stderr}`.trim();
    if (failureOut.length > 0) process.stderr.write(`${failureOut}\n`);
    return undefined;
  }
  const upCombined = `${up.stdout}\n${up.stderr}`.trim();
  if (upCombined.length > 0) {
    process.stdout.write(`${upCombined}\n`);
  }
  if (looksLikeTailscaleFailure(upCombined)) {
    process.stderr.write(
      "[sandalphone] tailscale reported a local CLI/daemon error; check `tailscale status` in this same shell\n",
    );
    return undefined;
  }

  // Prefer immediate URL from `tailscale funnel --bg --yes <port>` output.
  const fromUpOutput = extractFunnelUrlFromText(upCombined) ?? "";
  if (fromUpOutput.length > 0) {
    const normalized = normalizePublicBaseUrl(fromUpOutput);
    updateEnvFile(envPath, { PUBLIC_BASE_URL: normalized }, context.projectRoot);
    return normalized;
  }
  process.stdout.write("[sandalphone] no URL found directly in tailscale output; polling status...\n");

  // In --bg mode Tailscale may take a moment before status reflects funnel config.
  const resolved = resolveFunnelUrlWithRetries();
  if (resolved === undefined) return undefined;
  const resolvedUrl = normalizePublicBaseUrl(resolved!);
  updateEnvFile(envPath, { PUBLIC_BASE_URL: resolvedUrl }, context.projectRoot);
  return resolvedUrl;
}

function detectFunnelUrlFromPlainStatus(): string | undefined {
  const plain = runCommandCapture("tailscale", ["funnel", "status"], { timeoutMs: 7000 });
  if (plain.status !== 0) return undefined;
  const combined = `${plain.stdout}\n${plain.stderr}`.trim();
  if (combined.length > 0) process.stdout.write(`${combined}\n`);
  if (looksLikeTailscaleFailure(combined)) return undefined;
  return extractFunnelUrlFromText(combined);
}

function extractFunnelEnableUrl(output: string): string | undefined {
  return output.match(/https:\/\/login\.tailscale\.com\/f\/funnel\?[^\s"'`]+/)?.[0];
}

function resolveFunnelUrlWithRetries(): string | undefined {
  process.stdout.write("[sandalphone] reading funnel status...\n");
  for (let attempt = 1; attempt <= 20; attempt += 1) {
    process.stdout.write(`[sandalphone] status attempt ${attempt}/20\n`);
    const status = runCommandCapture("tailscale", ["funnel", "status", "--json"], {
      timeoutMs: 7000,
    });
    if (!status.timedOut && status.status === 0) {
      const fromJson = extractFunnelUrl(`${status.stdout}\n${status.stderr}`);
      if (fromJson) return fromJson;
    }

    const fromPlain = detectFunnelUrlFromPlainStatus();
    if (fromPlain) return fromPlain;

    if (attempt < 20) sleepMs(1000);
  }

  return undefined;
}

function printManualFunnelUrlSteps(port: string): void {
  process.stdout.write("  manual URL discovery:\n");
  process.stdout.write(`    1) sandalphone funnel up --port ${port}\n`);
  process.stdout.write("    2) sandalphone funnel status\n");
  process.stdout.write("    3) if needed, run: tailscale funnel status\n");
  process.stdout.write("    4) copy the https://... host and paste it as PUBLIC_BASE_URL\n");
}

function updateEnvFile(envPath: string, updates: EnvMap, projectRoot: string): void {
  const templatePath = resolve(projectRoot, ".env.example");
  const sourceText = existsSync(envPath)
    ? readFileSync(envPath, "utf8")
    : existsSync(templatePath)
      ? readFileSync(templatePath, "utf8")
      : "";

  const merged = removeEnvKeys(applyEnvUpdates(sourceText, updates), ["DESTINATION_PHONE_E164"]);
  writeFileSync(envPath, merged.endsWith("\n") ? merged : `${merged}\n`, "utf8");
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

async function promptWithHelp(
  rl: ReturnType<typeof createInterface>,
  label: string,
  defaultValue: string | undefined,
  helpLines: string[],
): Promise<string> {
  while (true) {
    const value = await prompt(rl, label, { defaultValue, secret: true });
    if (value.length > 0) return value;
    process.stdout.write(`\n[sandalphone] ${label} is required for real-time translation.\n`);
    for (const line of helpLines) {
      process.stdout.write(`${line}\n`);
    }
    const skip = await promptYesNo(rl, "Skip for now?", false);
    if (skip) return "";
  }
}

async function promptYesNo(
  rl: ReturnType<typeof createInterface>,
  label: string,
  defaultYes: boolean,
): Promise<boolean> {
  const defaultToken = defaultYes ? "Y/n" : "y/N";

  while (true) {
    const raw = await rl.question(`${label} [${defaultToken}]: `);
    const normalized = raw.trim().toLowerCase();

    if (!normalized) return defaultYes;
    if (normalized === "y" || normalized === "yes") return true;
    if (normalized === "n" || normalized === "no") return false;

    process.stdout.write("  enter y or n\n");
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
  if (mode !== "deploy" && mode !== "local" && mode !== "callpath") {
    die(`unknown doctor mode: ${mode}`);
  }

  const { flags } = parseFlags(args.slice(1));
  const env: Dict = {};
  if (flags["env-path"]) {
    env.ENV_PATH = resolve(context.projectRoot, flags["env-path"]);
  }

  if (mode === "local") {
    runNodeScript("scripts/doctor-local.mjs", context, env);
    return;
  }
  if (mode === "callpath") {
    if (flags["base-url"]) env.BASE_URL = flags["base-url"];
    if (flags["session-id"]) env.SESSION_ID = flags["session-id"];
    if (flags.secret) env.CONTROL_API_SECRET = flags.secret;
    runNodeScript("scripts/doctor-callpath.mjs", context, env);
    return;
  }

  runNodeScript("scripts/deploy-preflight.mjs", context, env);
}

function handleUrls(args: string[], context: CliContext): void {
  const { flags } = parseFlags(args);
  const envPath = resolve(context.projectRoot, flags["env-path"] ?? ".env");
  const envText = existsSync(envPath) ? readFileSync(envPath, "utf8") : "";
  const env = parseEnvFile(envText);

  const baseUrl = normalizePublicBaseUrl(flags["base-url"] ?? env.PUBLIC_BASE_URL ?? "");
  if (!baseUrl) {
    die("PUBLIC_BASE_URL is required. Set it in .env or pass --base-url https://...");
  }
  if (!/^https:\/\//.test(baseUrl)) {
    die("PUBLIC_BASE_URL must be HTTPS for Twilio webhooks");
  }

  process.stdout.write(`[sandalphone] base url: ${baseUrl}\n`);
  process.stdout.write(`[sandalphone] Twilio Voice webhook: ${baseUrl}/twilio/voice\n`);
  process.stdout.write(`[sandalphone] Twilio Media Stream WS: wss://${stripScheme(baseUrl)}/twilio/stream\n`);
}

async function handleOpenClaw(args: string[], context: CliContext): Promise<void> {
  const action = args[0] ?? "help";
  if (action === "help") {
    printOpenClawHelp();
    return;
  }
  if (action !== "command") {
    die(`unknown openclaw action: ${action}`);
  }

  const { flags, extras } = parseFlags(args.slice(1));
  const baseUrl = resolveGatewayBaseUrl(context, flags);

  const command = flags.command ?? extras.join(" ").trim();
  if (!command) {
    die("openclaw command text is required (--command \"...\" or positional text)");
  }

  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  const controlSecret = resolveControlSecret(context, flags);
  if (controlSecret) {
    headers["x-control-secret"] = controlSecret;
  }

  const response = await fetch(`${baseUrl}/openclaw/command`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      command,
      sessionId: flags["session-id"],
      callId: flags["call-id"],
      source: flags.source,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    die(`openclaw command failed with ${response.status}: ${body.slice(0, 300)}`);
  }
  process.stdout.write("[sandalphone] openclaw command accepted\n");
}

async function handleSession(args: string[], context: CliContext): Promise<void> {
  const action = args[0] ?? "help";
  if (action === "help") {
    printSessionHelp();
    return;
  }

  const { flags } = parseFlags(args.slice(1));
  const baseUrl = resolveGatewayBaseUrl(context, flags);
  const headers: Record<string, string> = {};
  const controlSecret = resolveControlSecret(context, flags);
  if (controlSecret) {
    headers["x-control-secret"] = controlSecret;
  }

  if (action === "list") {
    const response = await fetch(`${baseUrl}/sessions`, { headers });
    if (!response.ok) {
      const body = await response.text();
      die(`session list failed with ${response.status}: ${body.slice(0, 300)}`);
    }
    const payload = (await response.json()) as {
      sessions?: Array<{
        id: string;
        source: string;
        state: string;
        mode: string;
        sourceLanguage: string;
        targetLanguage: string;
      }>;
    };
    const sessions = payload.sessions ?? [];
    if (sessions.length === 0) {
      process.stdout.write("[sandalphone] no sessions found\n");
      return;
    }
    for (const session of sessions) {
      process.stdout.write(
        `${session.id} source=${session.source} state=${session.state} mode=${session.mode} lang=${session.sourceLanguage}->${session.targetLanguage}\n`,
      );
    }
    return;
  }

  if (action === "set") {
    const sessionId = flags["session-id"];
    const callId = flags["call-id"];
    if (!sessionId && !callId) {
      die("session set requires --session-id or --call-id");
    }
    if (!flags.mode && !flags["source-language"] && !flags["target-language"]) {
      die("session set requires --mode and/or language flags");
    }
    const response = await fetch(`${baseUrl}/sessions/control`, {
      method: "POST",
      headers: {
        ...headers,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        sessionId,
        callId,
        source: flags.source,
        mode: flags.mode,
        sourceLanguage: flags["source-language"],
        targetLanguage: flags["target-language"],
      }),
    });
    if (!response.ok) {
      const body = await response.text();
      die(`session set failed with ${response.status}: ${body.slice(0, 300)}`);
    }
    process.stdout.write("[sandalphone] session updated\n");
    return;
  }

  if (action === "debug") {
    const sessionId = flags["session-id"];
    if (!sessionId) {
      die("session debug requires --session-id");
    }
    const response = await fetch(`${baseUrl}/sessions/${encodeURIComponent(sessionId)}/debug`, {
      headers,
    });
    if (!response.ok) {
      const body = await response.text();
      die(`session debug failed with ${response.status}: ${body.slice(0, 300)}`);
    }
    process.stdout.write(`${JSON.stringify(await response.json(), null, 2)}\n`);
    return;
  }

  die(`unknown session action: ${action}`);
}

function resolveGatewayBaseUrl(context: CliContext, flags: Record<string, string>): string {
  const envPath = resolve(context.projectRoot, flags["env-path"] ?? ".env");
  const envText = existsSync(envPath) ? readFileSync(envPath, "utf8") : "";
  const env = parseEnvFile(envText);
  const baseUrl = normalizePublicBaseUrl(
    flags["base-url"] ?? env.PUBLIC_BASE_URL ?? `http://127.0.0.1:${env.PORT ?? "8080"}`,
  );
  return baseUrl;
}

function resolveControlSecret(context: CliContext, flags: Record<string, string>): string {
  if (flags.secret) return flags.secret;
  const envPath = resolve(context.projectRoot, flags["env-path"] ?? ".env");
  const envText = existsSync(envPath) ? readFileSync(envPath, "utf8") : "";
  const env = parseEnvFile(envText);
  return env.CONTROL_API_SECRET ?? "";
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

  if (action === "print-launchd") {
    assertDarwin("print-launchd");
    const { flags } = parseFlags(args.slice(1));
    process.stdout.write(
      renderLaunchdPlist({
        label: flags.label ?? "com.sandalphone.vps-gateway",
        workdir: resolve(context.projectRoot),
        envFile: resolve(context.projectRoot, flags["env-path"] ?? ".env"),
        nodeBin: flags["node-bin"] ?? "node",
        stdoutLog: flags["stdout-log"] ?? "/tmp/sandalphone-vps-gateway.out.log",
        stderrLog: flags["stderr-log"] ?? "/tmp/sandalphone-vps-gateway.err.log",
      }),
    );
    return;
  }

  if (action === "install-launchd") {
    assertDarwin("install-launchd");
    const { flags } = parseFlags(args.slice(1));
    const label = flags.label ?? "com.sandalphone.vps-gateway";
    const output = expandHomePath(
      flags.output ?? `~/Library/LaunchAgents/${label}.plist`,
    );
    const envPath = resolve(context.projectRoot, flags["env-path"] ?? ".env");
    const plist = renderLaunchdPlist({
      label,
      workdir: resolve(context.projectRoot),
      envFile: envPath,
      nodeBin: flags["node-bin"] ?? "node",
      stdoutLog: flags["stdout-log"] ?? "/tmp/sandalphone-vps-gateway.out.log",
      stderrLog: flags["stderr-log"] ?? "/tmp/sandalphone-vps-gateway.err.log",
    });

    mkdirSync(dirname(output), { recursive: true });
    writeFileSync(output, plist, "utf8");
    process.stdout.write(`[sandalphone] installed launchd plist -> ${output}\n`);
    process.stdout.write(`[sandalphone] load with: sandalphone service launchd-load --label ${label} --plist ${output}\n`);
    return;
  }

  if (action === "launchd-load") {
    assertDarwin("launchd-load");
    const { flags } = parseFlags(args.slice(1));
    const label = flags.label ?? "com.sandalphone.vps-gateway";
    const plist = expandHomePath(
      flags.plist ?? `~/Library/LaunchAgents/${label}.plist`,
    );
    const domain = launchdDomain();

    runCommand("launchctl", ["bootout", domain, plist], { allowNonZeroExit: true });
    runCommand("launchctl", ["bootstrap", domain, plist]);
    runCommand("launchctl", ["enable", `${domain}/${label}`]);
    runCommand("launchctl", ["kickstart", "-k", `${domain}/${label}`]);
    process.stdout.write(`[sandalphone] launchd loaded: ${domain}/${label}\n`);
    return;
  }

  if (action === "launchd-unload") {
    assertDarwin("launchd-unload");
    const { flags } = parseFlags(args.slice(1));
    const label = flags.label ?? "com.sandalphone.vps-gateway";
    const plist = expandHomePath(
      flags.plist ?? `~/Library/LaunchAgents/${label}.plist`,
    );
    const domain = launchdDomain();

    runCommand("launchctl", ["disable", `${domain}/${label}`], { allowNonZeroExit: true });
    runCommand("launchctl", ["bootout", domain, plist], { allowNonZeroExit: true });
    process.stdout.write(`[sandalphone] launchd unloaded: ${domain}/${label}\n`);
    return;
  }

  if (action === "launchd-status") {
    assertDarwin("launchd-status");
    const { flags } = parseFlags(args.slice(1));
    const label = flags.label ?? "com.sandalphone.vps-gateway";
    runCommand("launchctl", ["print", `${launchdDomain()}/${label}`]);
    return;
  }

  if (action === "launchd-logs") {
    assertDarwin("launchd-logs");
    const { flags } = parseFlags(args.slice(1));
    const outPath = flags["stdout-log"] ?? "/tmp/sandalphone-vps-gateway.out.log";
    const errPath = flags["stderr-log"] ?? "/tmp/sandalphone-vps-gateway.err.log";
    process.stdout.write(`[sandalphone] stdout log: ${outPath}\n`);
    process.stdout.write(`[sandalphone] stderr log: ${errPath}\n`);
    runCommand("tail", ["-n", flags.lines ?? "200", outPath, errPath], {
      allowNonZeroExit: true,
    });
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
  opts: { cwd?: string; env?: NodeJS.ProcessEnv; allowNonZeroExit?: boolean } = {},
): void {
  const result = spawnSync(command, args, {
    cwd: opts.cwd,
    env: opts.env,
    stdio: "inherit",
  });

  if (result.error) {
    die(`failed to run ${command}: ${result.error.message}`);
  }

  if (!opts.allowNonZeroExit) {
    process.exit(result.status ?? 1);
  }
}

function runCommandCapture(
  command: string,
  args: string[],
  opts: { cwd?: string; env?: NodeJS.ProcessEnv; timeoutMs?: number } = {},
): CommandResult {
  const result = spawnSync(command, args, {
    cwd: opts.cwd,
    env: opts.env,
    encoding: "utf8",
    stdio: "pipe",
    timeout: opts.timeoutMs,
    killSignal: "SIGTERM",
  });

  return {
    status: result.status ?? 1,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
    error: result.error ?? undefined,
    timedOut: result.signal === "SIGTERM" && opts.timeoutMs !== undefined,
  };
}

function stripScheme(url: string): string {
  return url.replace(/^https?:\/\//, "");
}

function normalizePublicBaseUrl(url: string): string {
  return url.trim().replace(/\/+$/, "");
}

function sleepMs(ms: number): void {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    // intentional busy wait; used for short CLI retry delays
  }
}

function looksLikeTailscaleFailure(output: string): boolean {
  const normalized = output.toLowerCase();
  return (
    normalized.includes("failed to load preferences") ||
    normalized.includes("the tailscale cli failed to start") ||
    normalized.includes("failed to connect to local tailscale daemon") ||
    normalized.includes("not running?")
  );
}

function assertDarwin(action: string): void {
  if (platform() !== "darwin") {
    die(`service ${action} is only available on macOS`);
  }
}

function launchdDomain(): string {
  const uid = typeof process.getuid === "function" ? String(process.getuid()) : "";
  if (!uid) {
    die("unable to determine current uid for launchd domain");
  }
  return `gui/${uid}`;
}

function expandHomePath(input: string): string {
  if (input === "~") return homedir();
  if (input.startsWith("~/")) return resolve(homedir(), input.slice(2));
  return resolve(input);
}

function xmlEscape(input: string): string {
  return input
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&apos;");
}

function renderLaunchdPlist(values: {
  label: string;
  workdir: string;
  envFile: string;
  nodeBin: string;
  stdoutLog: string;
  stderrLog: string;
}): string {
  const templatePath = resolve(
    dirname(fileURLToPath(import.meta.url)),
    "..",
    "deploy/launchd/com.sandalphone.vps-gateway.plist",
  );
  const template = readFileSync(templatePath, "utf8");
  return template
    .replaceAll("__LABEL__", xmlEscape(values.label))
    .replaceAll("__WORKDIR__", xmlEscape(values.workdir))
    .replaceAll("__ENV_FILE__", xmlEscape(values.envFile))
    .replaceAll("__NODE_BIN__", xmlEscape(values.nodeBin))
    .replaceAll("__STDOUT_LOG__", xmlEscape(values.stdoutLog))
    .replaceAll("__STDERR_LOG__", xmlEscape(values.stderrLog));
}


function die(message: string): never {
  process.stderr.write(`[sandalphone] ${message}\n`);
  process.stderr.write("[sandalphone] run `sandalphone help` for usage\n");
  process.exit(1);
}

function printHelp(): void {
  process.stdout.write(`sandalphone ${cliVersion()}\n\n`);
  process.stdout.write(`Invocation:\n`);
  process.stdout.write(`  Global: sandalphone <command>\n`);
  process.stdout.write(`  Local:  node dist/cli.js <command>\n`);
  process.stdout.write(`  If global command is missing: cd /Users/matt/levi/vps-gateway && npm link\n\n`);
  process.stdout.write(`Usage:\n`);
  process.stdout.write(`  sandalphone install [--env-path PATH]\n`);
  process.stdout.write(`  sandalphone build|check|dev|start\n`);
  process.stdout.write(`  sandalphone test [all|smoke|quick]\n`);
  process.stdout.write(`  sandalphone smoke live [--base-url URL] [--secret SECRET] [--strict-egress]\n`);
  process.stdout.write(`  sandalphone urls [--env-path .env] [--base-url https://...]\n`);
  process.stdout.write(`  sandalphone openclaw command --command \"...\" [--base-url URL] [--secret SECRET]\n`);
  process.stdout.write(`  sandalphone session <list|set|debug>\n`);
  process.stdout.write(`  sandalphone funnel <action>\n`);
  process.stdout.write(`  sandalphone doctor deploy [--env-path .env]\n`);
  process.stdout.write(`  sandalphone doctor local [--env-path .env]\n`);
  process.stdout.write(`  sandalphone doctor callpath [--base-url URL] [--session-id ID] [--secret SECRET]\n`);
  process.stdout.write(`  sandalphone service <action>\n\n`);
  process.stdout.write(`Legacy alias: levi <command>\n\n`);
  printFunnelHelp();
  printSessionHelp();
  printServiceHelp();
}

function printFunnelHelp(): void {
  process.stdout.write(`Funnel actions:\n`);
  process.stdout.write(`  sandalphone funnel up [--port 8080] [--env-path .env]\n`);
  process.stdout.write(`  sandalphone funnel status\n`);
  process.stdout.write(`  sandalphone funnel reset [--clear-env] [--env-path .env]\n`);
  process.stdout.write(`\n`);
}

function printServiceHelp(): void {
  process.stdout.write(`Service actions:\n`);
  process.stdout.write(`  sandalphone service print-launchd [--label LABEL] [--env-path .env]\n`);
  process.stdout.write(`  sandalphone service install-launchd [--label LABEL] [--output ~/Library/LaunchAgents/..plist]\n`);
  process.stdout.write(`  sandalphone service launchd-load [--label LABEL] [--plist ~/Library/LaunchAgents/..plist]\n`);
  process.stdout.write(`  sandalphone service launchd-unload [--label LABEL] [--plist ~/Library/LaunchAgents/..plist]\n`);
  process.stdout.write(`  sandalphone service launchd-status [--label LABEL]\n`);
  process.stdout.write(`  sandalphone service launchd-logs [--lines N] [--stdout-log PATH] [--stderr-log PATH]\n`);
  process.stdout.write(`  sandalphone service print-unit\n`);
  process.stdout.write(`  sandalphone service install-unit [--output PATH]\n`);
  process.stdout.write(`  sandalphone service reload\n`);
  process.stdout.write(`  sandalphone service enable\n`);
  process.stdout.write(`  sandalphone service restart\n`);
  process.stdout.write(`  sandalphone service status\n`);
  process.stdout.write(`  sandalphone service logs [--lines N]\n`);
}

function printOpenClawHelp(): void {
  process.stdout.write(`OpenClaw actions:\n`);
  process.stdout.write(`  sandalphone openclaw command --command "research..." [--base-url URL] [--secret SECRET]\n`);
  process.stdout.write(`  sandalphone openclaw command "research..." [--base-url URL] [--secret SECRET]\n`);
  process.stdout.write(`\n`);
}

function printSessionHelp(): void {
  process.stdout.write(`Session actions:\n`);
  process.stdout.write(`  sandalphone session list [--base-url URL] [--secret SECRET]\n`);
  process.stdout.write(`  sandalphone session set --session-id ID --mode passthrough [--base-url URL] [--secret SECRET]\n`);
  process.stdout.write(`  sandalphone session set --call-id sip-123 --source voipms --target-language es\n`);
  process.stdout.write(`  sandalphone session debug --session-id ID\n`);
  process.stdout.write(`\n`);
}

function cliVersion(): string {
  try {
    const pkgPath = resolve(dirname(fileURLToPath(import.meta.url)), "..", "package.json");
    const parsed = JSON.parse(readFileSync(pkgPath, "utf8")) as { version?: string };
    return parsed.version ?? "0.0.0";
  } catch {
    return "0.0.0";
  }
}

void main(process.argv.slice(2)).catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  die(message);
});
