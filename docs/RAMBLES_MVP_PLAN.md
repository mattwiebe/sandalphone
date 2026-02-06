# RAMBLES MVP Plan (Revised)

Date: 2026-01-29

## Purpose
Deliver a 2-3 week MVP that maps directly to RAMBLES.txt priorities: voice-first walking mode, real-time translation, local-first automation, and reliable recovery/backup. This plan tightens scope and adds traceability to the vision.

## MVP Definition (2-3 Weeks)
A voice-first assistant that supports continuous walking-mode translation and core Mac automation with persistent memory, consent mode, and reliable backup/restore. Telegram is the only supported mobile channel for MVP.

## Non-Goals (MVP)
- Full multi-channel orchestration (Beeper, WhatsApp, SMS, Farcaster)
- Restaurant ops automation beyond basic task capture
- Full UI or iOS native app
- Large-scale agent swarm or heavy autonomous workflows

## Traceability (RAMBLES -> MVP Features)
| RAMBLES need | MVP feature | Notes |
| --- | --- | --- |
| Total voice interface / Jarvis on Mac | Voice command parser + AppleScript bridge | Core commands only (read email, send message, calendar) |
| Walking-mode continuous use | Persistent Telegram voice call session + reconnection | Only Telegram in MVP |
| Real-time Spanish/English translation | Duplex audio pipeline with streaming STT/TTS | Focused on phone conversation use case |
| Consent mode | Explicit consent script + command | Required before recording/translation mode |
| Text archive + audio archive | SQLite transcript + audio file retention | Basic file retention policy |
| Scan emails/docs, theme stubs | Minimal “theme stub” extractor | Only email subject + top themes summary |
| Task list surfacing | Voice command to create tasks + list tasks | Stored locally in SQLite |
| Cloud sync / laptop failure | Backup + restore runbook | Simple rsync + cloud path, optional encryption |
| Code diff summaries | “Explain last changes” command | Uses git to summarize recent diff |
| Nest Cam alerts | Phase 0.5 spike (optional) | Only if time allows; otherwise planned Phase B |

## MVP Architecture (Minimal Additions)
- Mac backend remains core (FastAPI + MLX pipeline)
- Telegram bot as single mobile gateway
- SQLite for transcripts, tasks, and theme stubs
- File storage for audio clips (M4A)
- Backup script + restore checklist

## Milestones

### Week 1: Foundations
- Storage: SQLite schema for transcripts, tasks, theme stubs
- Audio archive: save audio clip per session with metadata
- Consent mode: command + spoken script + state gate
- Voice commands (minimal set)
- Backup plan draft + basic script

Deliverables
- `mac/src/storage/` with simple models
- Consent mode state toggle
- Audio file retention policy
- `scripts/backup_levi.sh` + restore doc

### Week 2: Walking Translation MVP
- Duplex audio pipeline over Telegram call
- Reconnection handling (WiFi/LTE switch simulation)
- Translation latency targets (<2.5s P95)
- Minimal “walking mode” state with command to enter/exit

Deliverables
- `/ws/duplex` endpoint
- Telegram persistent call handler
- Reconnections logged and retryable

### Week 3: Smart Assist Layer
- Theme stub extractor for email summaries
- Task capture + list voice commands
- “Explain last changes” command using git
- Polishing: action item extraction baseline

Deliverables
- Theme stub creation + retrieval
- Task list management
- Code diff summarizer

## Acceptance Criteria
- Walking mode call + real-time translation works end-to-end
- Consent mode prevents recording until accepted
- Transcripts + audio saved and searchable
- Tasks can be created and listed by voice
- Backups can be restored onto a new Mac
- Code changes can be summarized by command

## Decisions and Constraints
- Single mobile channel: Telegram only
- Mac-first architecture, no native iOS app
- Local-first processing with optional cloud calls
- Keep dependencies minimal and Mac-compatible

## Risks and Mitigations
- Latency too high: reduce model size, cache, trim context
- Reconnection failures: exponential backoff + user ping
- Storage bloat: rolling retention policy + compression
- Backup failures: weekly restore drill

## Appendix: Consent Script (Draft)
"I record this conversation to translate in real time. Do you consent to recording and automated translation?"

## Appendix: Backup Plan (Draft)
- Daily: rsync SQLite + audio to cloud path
- Weekly: restore drill to a spare directory
- Optional: encrypt backups with age or gpg
