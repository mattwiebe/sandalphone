import { loadConfig } from "./config.js";
import { SessionStore } from "./pipeline/session-store.js";
import { VoiceOrchestrator } from "./pipeline/orchestrator.js";
import { AssemblyAiStreamingProvider } from "./providers/stt/assemblyai.js";
import { GoogleTranslationProvider } from "./providers/translation/google.js";
import { PollyStandardProvider } from "./providers/tts/polly.js";
import { makeLogger } from "./server/logger.js";
import { startHttpServer } from "./server/http.js";

function main(): void {
  const config = loadConfig(process.env);
  const logger = makeLogger(config.logLevel);

  const orchestrator = new VoiceOrchestrator({
    logger,
    sessionStore: new SessionStore(),
    stt: new AssemblyAiStreamingProvider(),
    translator: new GoogleTranslationProvider(),
    tts: new PollyStandardProvider(),
    destination phoneE164: config.destination phoneE164,
  });

  startHttpServer(config.port, logger, orchestrator);
}

main();
