import type { AppConfig } from "../config.js";
import type { Logger } from "../server/logger.js";
import type { StreamingSttProvider, TranslationProvider, TtsProvider } from "../domain/providers.js";
import { AssemblyAiRealtimeProvider, StubAssemblyAiProvider } from "./stt/assemblyai.js";
import { GoogleTranslationProvider, StubGoogleTranslationProvider } from "./translation/google.js";
import { GoogleTtsProvider } from "./tts/google.js";
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
    : new StubAssemblyAiProvider(config.stubSttText ?? "");

  const translator = config.googleTranslateApiKey
    ? new GoogleTranslationProvider({ apiKey: config.googleTranslateApiKey })
    : new StubGoogleTranslationProvider();

  let tts: TtsProvider;
  if (config.ttsProvider === "google") {
    tts = config.googleTtsApiKey
      ? new GoogleTtsProvider({
          apiKey: config.googleTtsApiKey,
          voiceEn: config.googleTtsVoiceEn,
          voiceEs: config.googleTtsVoiceEs,
        })
      : new StubPollyProvider();
  } else if (process.env.DISABLE_POLLY === "1") {
    tts = new StubPollyProvider();
  } else {
    tts = new PollyStandardProvider({
      region: config.awsRegion,
      voiceEn: config.pollyVoiceEn,
      voiceEs: config.pollyVoiceEs,
    });
  }

  logger.info("provider selection", {
    stt: stt.name,
    translation: translator.name,
    tts: tts.name,
  });

  return { stt, translator, tts };
}
