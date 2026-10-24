# Collect the authentic agent trace after this session

This is a checklist, not a fabricated trace export. The active rollout is still
being written and must not be represented as complete.

Current session:
- Harness: Codex Desktop (`originator` in session metadata).
- Runtime model: `gpt-6-astra` (`turn_context.model`).
- Session ID: `01a16e15-a4c7-7c83-803f-e748ed4e5c46`.
- Rollout relative to Codex sessions root:
  `2026/10/24/rollout-2026-10-24T19-24-34-01a16e15-a4c7-7c83-803f-e748ed4e5c46.jsonl`.

1. Finish this session and quit Codex so the rollout is fully flushed.
2. Identify every other challenge session by project path/session metadata.
   Do not include unrelated chats or reconstruct missing history.
3. Copy relevant original rollouts from `$CODEX_HOME/sessions/` (normally
   `~/.codex/sessions/`) into `agent-trace/codex/`, preserving date directories.
4. Review copies for secrets and private personal information. Redact in the
   staged copies, preserving JSONL structure. Never copy `auth.json`, settings,
   credential stores, or the entire Codex directory.
5. Zip the staged `agent-trace/` directory as `agent-trace.zip`, separately from
   `code.zip`. Inspect the archive before sharing.
6. Submit the authentic root `log.txt` separately as the conversation summary.

The source archive excludes log.txt and raw rollouts because they are separate
submission artifacts and may contain local context. Development model usage is
not inferred from OCR runtime usage; the usage report says which quantities are
actually measured.
