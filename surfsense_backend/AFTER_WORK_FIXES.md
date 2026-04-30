# After Work Fixes

## Middleware Risk Flags (new_chat)

These are known "policy/routing via middleware" risks to review later.

1. `FileIntentMiddleware`
- Risk: `file_write` classification can force `write_file`/`edit_file` and override deliverable or connector tool selection.
- Example failure: user asks for video/report artifact, agent writes into `/documents/*` instead.

2. `KnowledgePriorityMiddleware`
- Risk: KB planner and injected priority hints can over-anchor turns to KB reads when connector action is the better path.

3. `KnowledgeTreeMiddleware`
- Risk: injected workspace tree can bias behavior toward file navigation/writes by default.

4. `SurfSenseFilesystemMiddleware` + `KnowledgeBasePersistenceMiddleware`
- Risk: mistaken `write_file` actions become persisted NOTE documents in KB, making wrong-path behavior durable.

5. `PermissionMiddleware`
- Risk: deny/ask rules can hide or block the correct tool, appearing as "model chose wrong tool" when it never had access.

6. Subagent middleware parity (`chat_deepagent.py`)
- Risk: parent vs subagent stack differences can produce inconsistent behavior across similar tasks.

7. `SpillingContextEditingMiddleware` + compaction
- Risk: context trimming can remove critical tool evidence and cause wrong retries/tool choices.

8. `ToolCallNameRepairMiddleware`
- Risk: malformed calls may be auto-repaired to unintended tools in edge cases.

9. `DedupHITLToolCallsMiddleware` / `DoomLoopMiddleware`
- Risk: legitimate repeated calls can be suppressed or stopped early.

10. `MemoryInjectionMiddleware`
- Risk: injected memory may bias tool choice away from fresh connector/KB evidence.
