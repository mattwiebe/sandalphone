export interface AppConfig {
  readonly port: number;
  readonly destination phoneE164: string;
  readonly logLevel: "debug" | "info" | "warn" | "error";
  readonly asteriskSharedSecret?: string;
  readonly pipelineMinFrameIntervalMs: number;
  readonly assemblyAiApiKey?: string;
  readonly assemblyAiRealtimeUrl?: string;
  readonly googleTranslateApiKey?: string;
  readonly awsRegion: string;
  readonly pollyVoiceEn: string;
  readonly pollyVoiceEs: string;
}

export function loadConfig(env: NodeJS.ProcessEnv): AppConfig {
  const port = Number(env.PORT ?? "8080");
  if (!Number.isFinite(port) || port <= 0) {
    throw new Error(`Invalid PORT: ${env.PORT}`);
  }

  const destination phoneE164 = env.DESTINATION_PHONE_E164 ?? "+15555550100";
  const logLevel = (env.LOG_LEVEL ?? "info") as AppConfig["logLevel"];
  const pipelineMinFrameIntervalMs = Number(env.PIPELINE_MIN_FRAME_INTERVAL_MS ?? "400");
  if (!Number.isFinite(pipelineMinFrameIntervalMs) || pipelineMinFrameIntervalMs < 0) {
    throw new Error(
      `Invalid PIPELINE_MIN_FRAME_INTERVAL_MS: ${env.PIPELINE_MIN_FRAME_INTERVAL_MS}`,
    );
  }

  return {
    port,
    destination phoneE164,
    logLevel,
    asteriskSharedSecret: env.ASTERISK_SHARED_SECRET,
    pipelineMinFrameIntervalMs,
    assemblyAiApiKey: env.ASSEMBLYAI_API_KEY,
    assemblyAiRealtimeUrl: env.ASSEMBLYAI_REALTIME_URL,
    googleTranslateApiKey: env.GOOGLE_TRANSLATE_API_KEY,
    awsRegion: env.AWS_REGION ?? "us-west-2",
    pollyVoiceEn: env.POLLY_VOICE_EN ?? "Joanna",
    pollyVoiceEs: env.POLLY_VOICE_ES ?? "Lupe",
  };
}
