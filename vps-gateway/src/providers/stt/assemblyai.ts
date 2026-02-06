import type { StreamingSttProvider } from "../../domain/providers.js";
import type { AudioFrame, TranscriptionChunk } from "../../domain/types.js";

export class AssemblyAiStreamingProvider implements StreamingSttProvider {
  public readonly name = "assemblyai";

  public async transcribe(frame: AudioFrame): Promise<TranscriptionChunk | null> {
    // Stub for scaffold: replace with AssemblyAI real-time websocket integration.
    return {
      sessionId: frame.sessionId,
      text: "",
      isFinal: false,
      language: "es",
      timestampMs: Date.now(),
    };
  }
}
