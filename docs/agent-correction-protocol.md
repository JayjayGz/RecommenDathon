# Learning from workflow mistakes

## Source and scope

Adapted from the user-provided English `de-la-consigne-au-pipeline-en.html` (From an instruction to a self-correcting pipeline) and French `de-la-consigne-au-pipeline.html` (De la consigne au pipeline qui se corrige), supplied from Downloads on 2026-11-14. Both describe ten levels. Their examples, lab statistics, Copilot paths, model results and tool names belong to that workshop. They are not measurements of AlphaForge and do not establish that tools, hooks or permissions exist here. The underlying lab files cited by the slides were not supplied.

This protocol makes corrections durable through repository files. It does not train model weights, promise recall without reading those files, or install an autonomous scheduler. It governs development agents; production investor profiles and raw model prompts do not belong in the lessons file.

## Before work

1. Load the requested role files and applicable entries from `memory/lessons.json`. Match both role and trigger; respect exclusions. Report loaded role names and lesson IDs so loading is observable. Do not load unrelated incident histories.
2. Identify required inputs, expected output artifacts and checks before editing. Confirm needed tools actually exist and work; a missing tool is a setup failure, not a failed business task.
3. Check current artifacts and relevant review versions. Do not trust a previous success message or approval of an older input. Prefer content hashes for review identity; timestamps alone can be misleading.
4. For a proposed restriction, distinguish a written instruction from enforced permissions. These Markdown roles do not grant or revoke capabilities. If a runner is later added, configure its real allowlist and verify both a permitted action and a forbidden action. Do not copy fictitious tool names from the slides.

## Correction loop

1. **Name the defect precisely.** Describe the trigger, expected behavior and observed mismatch. For example, "unknown evidence ID accepted" is useful; "be more careful" is not. If the cause is unproven, write `cause undetermined`.
2. **Preserve evidence.** Record a repository file/check reference or a concise redacted user correction. Preserve original failed outputs when available; never manufacture missing evidence, edit expected results to match a bug, or overwrite an old failure with a successful retry. Do not store secrets, personal investor information or full raw prompts in development memory.
3. **Bound the repair.** Route to the responsible role. Repair the implementation or the smallest applicable rule. Do not relax the profile's constraints, disable the gate, or rewrite measured facts. For risky mechanical repairs, work on a fixture or copy first. Routine authorized edits continue without a new approval flow.
4. **Replay the case.** For implemented behavior, run the reproducer and at least one nearby valid case to catch an overly broad fix. Replay existing relevant regressions; record actual commands and outcomes. For a documentation-only correction, inspect the resulting files and run applicable structural checks. Distinguish hypothetical failure cases from observed incidents.
5. **Record the lesson.** Add or update a record in `memory/lessons.json` with the fields below. Start as `documented`; use `verified` only with actual verification commands and results. A structural check proves structure, not model behavior or business correctness. Merge duplicate lessons and mark replaced ones `superseded` rather than accumulating contradictory rules.
6. **Close the loop.** Re-read the saved lesson, load it on the next relevant request and include its ID in the handoff. If a verified lesson fails again, return it to `documented`, preserve prior verification history in the record's evidence, and add the new failure. Never silently keep a disproven success label.

Use at most two repair attempts per distinct development defect during a task. If the same defect persists, report the blocker with evidence and continue independent work; do not loop indefinitely. This development limit does not add attempts to the application's initial explanation plus two repair generations and one checked template fallback.

## Lesson record

The JSON file has `schema_version: 1` and a `lessons` array. Each record contains:

| Field | Meaning |
| --- | --- |
| `id` | Unique `L-NNN` identifier; retain it when refining the same lesson |
| `roles` | Existing role names or `all` |
| `trigger` | Concrete situation where the lesson applies |
| `boundary` | Situations where it does not apply |
| `defect` | Actual observed failure or user correction |
| `cause` | Supported cause, or `cause undetermined` |
| `evidence` | Nonempty list of redacted observations and file/check references |
| `prevention` | Specific action or check that prevents recurrence |
| `regression` | Failing-case check and nearby valid case to replay |
| `status` | `documented`, `verified`, or `superseded` |
| `verification` | List of objects with actual `command`, `result`, `scope`; empty until run |

The first records are documented corrections from this conversation. They are not claims about application failures or measured agent improvement. Use the same shape for future records; do not insert invented examples into the live history.

## Applying the ten levels here

| Workshop level | AlphaForge adaptation | Current limit |
| --- | --- | --- |
| 1. Name the case | Explicit filename convention and precise defect/trigger fields | Text still requires loading and adherence |
| 2. Scope rules | Small root router, role-specific boundaries, filtered lessons | Avoid copying the full history into every agent |
| 3. Specialize | Use/avoid/capability sections on each role | Actual tool limits require runner configuration |
| 4. Load procedures on demand | Load this protocol only after role selection | This document is a playbook, not an installed skill |
| 5. Template and script | Structured lesson format and local validation script | Financial calculations still need implementation/tests |
| 6. Mechanical guards | Structural checker exits nonzero on invalid setup; runtime gates remain required | No hook or CI enforcement installed by this change |
| 7. Verify handoffs | Read actual artifacts, validate content and input identity | Role switching alone is not independent review |
| 8. Resume from artifacts | Reconstruct progress from verified outputs; invalidate stale descendants | No daemon, state engine or automatic resume implemented |
| 9. Correct the mechanism | Capability probes, current-input review, bounded repairs and regression replay | Missing infrastructure must not be marked as a business failure |
| 10. Memory and measurement | Persist named lessons and load them on relevant requests | Improvement must be measured here, never borrowed from slide statistics |

If a resumable runner is implemented later, persist stage inputs/outputs and hashes, use atomic state transitions and concurrency control, and let only the runner update stage status after verification. Resume only compatible outputs. Never treat an old accepted review as approval of revised content. Keep that separate from a background process that repeatedly invokes agents.

## Local verification

Run from the inner Git repository:

```powershell
python scripts/check_agent_workflow.py
python scripts/check_agent_workflow.py --self-test
python scripts/check_agent_workflow.py --lessons-for evidence
```

The checker reads files only. It checks routing, flat filenames, required role sections and lesson structure; it does not call models, execute stored verification commands, contact AWS or prove that agents obey instructions. Its self-tests inject malformed records and a valid control so a checker that rejects everything cannot pass.

To measure behavioral improvement later, preserve equivalent prompts, fixtures, model/settings and scoring rules; compare without/with the relevant lesson and include out-of-scope valid cases. Report actual pass counts, sample sizes, tool failures, cost and limitations. Do not estimate test counts or call a single repair general improvement.
