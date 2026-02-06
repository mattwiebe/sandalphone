import { randomUUID } from "node:crypto";
import type { CallSession, IncomingCallEvent, SessionState } from "../domain/types.js";

export class SessionStore {
  private readonly sessions = new Map<string, CallSession>();
  private readonly externalToInternal = new Map<string, string>();

  public createFromIncoming(event: IncomingCallEvent, targetPhoneE164: string): CallSession {
    const id = randomUUID();
    const session: CallSession = {
      id,
      source: event.source,
      inboundCaller: event.from,
      startedAtMs: event.receivedAtMs,
      targetPhoneE164,
      mode: "private_translation",
      sourceLanguage: "es",
      targetLanguage: "en",
      state: "pending",
    };

    this.sessions.set(id, session);
    this.externalToInternal.set(`${event.source}:${event.externalCallId}`, id);

    return session;
  }

  public getByExternal(source: string, externalCallId: string): CallSession | undefined {
    const internalId = this.externalToInternal.get(`${source}:${externalCallId}`);
    if (!internalId) return undefined;
    return this.sessions.get(internalId);
  }

  public get(id: string): CallSession | undefined {
    return this.sessions.get(id);
  }

  public all(): CallSession[] {
    return [...this.sessions.values()];
  }

  public updateState(id: string, state: SessionState): CallSession | undefined {
    const existing = this.sessions.get(id);
    if (!existing) return undefined;
    existing.state = state;
    return existing;
  }
}
