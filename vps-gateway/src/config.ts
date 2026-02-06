export interface AppConfig {
  readonly port: number;
  readonly destination phoneE164: string;
  readonly logLevel: "debug" | "info" | "warn" | "error";
}

export function loadConfig(env: NodeJS.ProcessEnv): AppConfig {
  const port = Number(env.PORT ?? "8080");
  if (!Number.isFinite(port) || port <= 0) {
    throw new Error(`Invalid PORT: ${env.PORT}`);
  }

  const destination phoneE164 = env.DESTINATION_PHONE_E164 ?? "+15555550100";
  const logLevel = (env.LOG_LEVEL ?? "info") as AppConfig["logLevel"];

  return {
    port,
    destination phoneE164,
    logLevel,
  };
}
