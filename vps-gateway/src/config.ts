export interface AppConfig {
  readonly port: number;
  readonly outboundTargetE164: string;
  readonly logLevel: "debug" | "info" | "warn" | "error";
  readonly asteriskSharedSecret?: string;
  readonly pipelineMinFrameIntervalMs: number;
  readonly assemblyAiApiKey?: string;
  readonly assemblyAiRealtimeUrl?: string;
  readonly googleTranslateApiKey?: string;
  readonly awsRegion: string;
  readonly pollyVoiceEn: string;
  readonly pollyVoiceEs: string;
  readonly egressMaxQueuePerSession: number;
  readonly stubSttText?: string;
  readonly twilioAuthToken?: string;
  readonly publicBaseUrl?: string;
  readonly controlApiSecret?: string;
  readonly openClawBridgeUrl?: string;
  readonly openClawBridgeApiKey?: string;
  readonly openClawBridgeTimeoutMs: number;
}

export function loadConfig(env: NodeJS.ProcessEnv): AppConfig {
  const port = Number(env.PORT ?? "8080");
  if (!Number.isFinite(port) || port <= 0) {
    throw new Error(`Invalid PORT: ${env.PORT}`);
  }

  const outboundTargetE164 =
    env.OUTBOUND_TARGET_E164 ?? env.DESTINATION_PHONE_E164 ?? "+15555550100";
  const logLevel = (env.LOG_LEVEL ?? "info") as AppConfig["logLevel"];
  const pipelineMinFrameIntervalMs = Number(env.PIPELINE_MIN_FRAME_INTERVAL_MS ?? "400");
  if (!Number.isFinite(pipelineMinFrameIntervalMs) || pipelineMinFrameIntervalMs < 0) {
    throw new Error(
      `Invalid PIPELINE_MIN_FRAME_INTERVAL_MS: ${env.PIPELINE_MIN_FRAME_INTERVAL_MS}`,
    );
  }
  const egressMaxQueuePerSession = Number(env.EGRESS_MAX_QUEUE_PER_SESSION ?? "64");
  if (!Number.isFinite(egressMaxQueuePerSession) || egressMaxQueuePerSession < 1) {
    throw new Error(`Invalid EGRESS_MAX_QUEUE_PER_SESSION: ${env.EGRESS_MAX_QUEUE_PER_SESSION}`);
  }
  const openClawBridgeTimeoutMs = Number(env.OPENCLAW_BRIDGE_TIMEOUT_MS ?? "1200");
  if (!Number.isFinite(openClawBridgeTimeoutMs) || openClawBridgeTimeoutMs < 100) {
    throw new Error(`Invalid OPENCLAW_BRIDGE_TIMEOUT_MS: ${env.OPENCLAW_BRIDGE_TIMEOUT_MS}`);
  }

  return {
    port,
    outboundTargetE164,
    logLevel,
    asteriskSharedSecret: env.ASTERISK_SHARED_SECRET,
    pipelineMinFrameIntervalMs,
    assemblyAiApiKey: env.ASSEMBLYAI_API_KEY,
    assemblyAiRealtimeUrl: env.ASSEMBLYAI_REALTIME_URL,
    googleTranslateApiKey: env.GOOGLE_TRANSLATE_API_KEY,
    awsRegion: env.AWS_REGION ?? "us-west-2",
    pollyVoiceEn: env.POLLY_VOICE_EN ?? "Joanna",
    pollyVoiceEs: env.POLLY_VOICE_ES ?? "Lupe",
    egressMaxQueuePerSession,
    stubSttText: env.STUB_STT_TEXT,
    twilioAuthToken: env.TWILIO_AUTH_TOKEN,
    publicBaseUrl: env.PUBLIC_BASE_URL,
    controlApiSecret: env.CONTROL_API_SECRET,
    openClawBridgeUrl: env.OPENCLAW_BRIDGE_URL,
    openClawBridgeApiKey: env.OPENCLAW_BRIDGE_API_KEY,
    openClawBridgeTimeoutMs,
  };
}
