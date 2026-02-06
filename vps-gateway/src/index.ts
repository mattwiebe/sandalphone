import { loadConfig } from "./config.js";
import { SessionStore } from "./pipeline/session-store.js";
import { VoiceOrchestrator } from "./pipeline/orchestrator.js";
import { makeProviders } from "./providers/factory.js";
import { makeLogger } from "./server/logger.js";
import { startHttpServer } from "./server/http.js";

function main(): void {
  const config = loadConfig(process.env);
  const logger = makeLogger(config.logLevel);
  const providers = makeProviders(config, logger);

  const orchestrator = new VoiceOrchestrator({
    logger,
    sessionStore: new SessionStore(),
    stt: providers.stt,
    translator: providers.translator,
    tts: providers.tts,
    destination phoneE164: config.destination phoneE164,
    minFrameIntervalMs: config.pipelineMinFrameIntervalMs,
  });

  const server = startHttpServer(config.port, logger, orchestrator, {
    asteriskSharedSecret: config.asteriskSharedSecret,
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
