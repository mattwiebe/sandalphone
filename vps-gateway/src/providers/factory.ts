import type { AppConfig } from "../config.js";
import type { Logger } from "../server/logger.js";
import type { StreamingSttProvider, TranslationProvider, TtsProvider } from "../domain/providers.js";
import { AssemblyAiRealtimeProvider, StubAssemblyAiProvider } from "./stt/assemblyai.js";
import { GoogleTranslationProvider, StubGoogleTranslationProvider } from "./translation/google.js";
import { PollyStandardProvider, StubPollyProvider } from "./tts/polly.js";

export type ProviderBundle = {
  readonly stt: StreamingSttProvider;
  readonly translator: TranslationProvider;
  readonly tts: TtsProvider;
};

export function makeProviders(config: AppConfig, logger: Logger): ProviderBundle {
  const stt = config.assemblyAiApiKey
    ? new AssemblyAiRealtimeProvider({
        apiKey: config.assemblyAiApiKey,
        url: config.assemblyAiRealtimeUrl,
      })
    : new StubAssemblyAiProvider();

  const translator = config.googleTranslateApiKey
    ? new GoogleTranslationProvider({ apiKey: config.googleTranslateApiKey })
    : new StubGoogleTranslationProvider();

  const tts =
    process.env.DISABLE_POLLY === "1"
      ? new StubPollyProvider()
      : new PollyStandardProvider({
          region: config.awsRegion,
          voiceEn: config.pollyVoiceEn,
          voiceEs: config.pollyVoiceEs,
        });

  logger.info("provider selection", {
    stt: stt.name,
    translation: translator.name,
    tts: tts.name,
  });

  return { stt, translator, tts };
}
