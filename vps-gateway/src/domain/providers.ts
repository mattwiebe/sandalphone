import type {
  AudioFrame,
  LanguageCode,
  TranscriptionChunk,
  TranslationChunk,
  TtsChunk,
} from "./types.js";

export interface StreamingSttProvider {
  readonly name: string;
  transcribe(frame: AudioFrame, sourceLanguage: LanguageCode): Promise<TranscriptionChunk | null>;
}

export interface TranslationProvider {
  readonly name: string;
  translate(chunk: TranscriptionChunk): Promise<TranslationChunk | null>;
}

export interface TtsProvider {
  readonly name: string;
  synthesize(chunk: TranslationChunk): Promise<TtsChunk | null>;
}
