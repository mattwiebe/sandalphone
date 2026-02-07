import { loadConfig } from "./config.js";
import { SessionStore } from "./pipeline/session-store.js";
import { VoiceOrchestrator } from "./pipeline/orchestrator.js";
import { EgressStore } from "./pipeline/egress-store.js";
import { makeProviders } from "./providers/factory.js";
import { makeLogger } from "./server/logger.js";
import { startHttpServer } from "./server/http.js";
import { makeOpenClawBridge } from "./integrations/openclaw.js";

function main(): void {
  const config = loadConfig(process.env);
  const logger = makeLogger(config.logLevel);
  const providers = makeProviders(config, logger);
  const egressStore = new EgressStore(config.egressMaxQueuePerSession);
  const openClawBridge = config.openClawBridgeUrl
    ? makeOpenClawBridge({
        endpointUrl: config.openClawBridgeUrl,
        apiKey: config.openClawBridgeApiKey,
        timeoutMs: config.openClawBridgeTimeoutMs,
        logger,
      })
    : undefined;
  let orchestratorRef: VoiceOrchestrator | undefined;

  const orchestrator = new VoiceOrchestrator({
    logger,
    sessionStore: new SessionStore(),
    stt: providers.stt,
    translator: providers.translator,
    tts: providers.tts,
    outboundTargetE164: config.outboundTargetE164,
    minFrameIntervalMs: config.pipelineMinFrameIntervalMs,
    onTtsChunk: (chunk) => {
      const enqueue = egressStore.enqueue(chunk);
      orchestratorRef?.reportEgressStats(chunk.sessionId, enqueue);
    },
    onSessionEvent: openClawBridge
      ? (event) => openClawBridge.publishSessionEvent(event)
      : undefined,
  });
  orchestratorRef = orchestrator;

  const server = startHttpServer(config.port, logger, orchestrator, {
    asteriskSharedSecret: config.asteriskSharedSecret,
    egressStore,
    twilioAuthToken: config.twilioAuthToken,
    publicBaseUrl: config.publicBaseUrl,
    controlApiSecret: config.controlApiSecret,
    openClawBridge,
  });

  const shutdown = (signal: NodeJS.Signals): void => {
    logger.info("shutdown signal received", { signal });
    server.close((error) => {
      if (error) {
        logger.error("failed to close http server", { error: error.message });
        process.exitCode = 1;
      }
      process.exit();
    });
  };

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
}

main();
