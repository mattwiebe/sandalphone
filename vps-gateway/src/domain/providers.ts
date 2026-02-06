import type { AudioFrame, TranscriptionChunk, TranslationChunk, TtsChunk } from "./types.js";

export interface StreamingSttProvider {
  readonly name: string;
  transcribe(frame: AudioFrame): Promise<TranscriptionChunk | null>;
}

export interface TranslationProvider {
  readonly name: string;
  translate(chunk: TranscriptionChunk): Promise<TranslationChunk | null>;
}

export interface TtsProvider {
  readonly name: string;
  synthesize(chunk: TranslationChunk): Promise<TtsChunk | null>;
}
