import type { AppConfig } from "../config.js";
import type { Logger } from "../server/logger.js";
import type { StreamingSttProvider, TranslationProvider, TtsProvider } from "../domain/providers.js";
import { GoogleSpeechProvider, StubGoogleSttProvider } from "./stt/google.js";
import { GoogleTranslationProvider, StubGoogleTranslationProvider } from "./translation/google.js";
import { GoogleTtsProvider, StubGoogleTtsProvider } from "./tts/google.js";

export type ProviderBundle = {
  readonly stt: StreamingSttProvider;
  readonly translator: TranslationProvider;
  readonly tts: TtsProvider;
};

export function makeProviders(config: AppConfig, logger: Logger): ProviderBundle {
  const stt = config.googleCloudApiKey
    ? new GoogleSpeechProvider({ apiKey: config.googleCloudApiKey })
    : new StubGoogleSttProvider(config.stubSttText ?? "");

  const translator = config.googleCloudApiKey
    ? new GoogleTranslationProvider({ apiKey: config.googleCloudApiKey })
    : new StubGoogleTranslationProvider();

  const tts: TtsProvider = config.googleCloudApiKey
    ? new GoogleTtsProvider({
        apiKey: config.googleCloudApiKey,
        voiceEn: config.googleTtsVoiceEn,
        voiceEs: config.googleTtsVoiceEs,
      })
    : new StubGoogleTtsProvider();

  logger.info("provider selection", {
    stt: stt.name,
    translation: translator.name,
    tts: tts.name,
  });

  return { stt, translator, tts };
}
