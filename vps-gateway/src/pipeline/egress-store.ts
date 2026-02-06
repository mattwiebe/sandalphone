import type { TtsChunk } from "../domain/types.js";

export class EgressStore {
  private readonly queues = new Map<string, TtsChunk[]>();

  public constructor(private readonly maxQueuePerSession: number) {}

  public enqueue(chunk: TtsChunk): void {
    const queue = this.queues.get(chunk.sessionId) ?? [];
    queue.push(chunk);
    if (queue.length > this.maxQueuePerSession) {
      queue.shift();
    }
    this.queues.set(chunk.sessionId, queue);
  }

  public dequeue(sessionId: string): TtsChunk | undefined {
    const queue = this.queues.get(sessionId);
    if (!queue || queue.length === 0) return undefined;

    const chunk = queue.shift();
    if (!chunk) return undefined;
    if (queue.length === 0) {
      this.queues.delete(sessionId);
    } else {
      this.queues.set(sessionId, queue);
    }
    return chunk;
  }

  public size(sessionId: string): number {
    return this.queues.get(sessionId)?.length ?? 0;
  }
}
