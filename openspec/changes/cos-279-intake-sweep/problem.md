# Problem: Nightly intake: one mcp-things call sweeps Inbox and Today, with item ages

Card: COS-279 · Project: mcp-fleet · Shape: feature · Domain: complicated

## Background
Casey, 23 Nov 2026, after COS-277. He decided that review and other meta tools stay in mcp-things as data packets, and that the judgment stays with Claude. Capture: "we run an intake every night through our casey-os setup, perhaps we can finetune that to use tools that help doing this more efficient?"

## Current state
- `~/dev/casey-os/skills/intake/SKILL.md` names no Things tool. Each night the sweep subagent picks its own calls: `get-tasks` once per list, `search-tasks` for Handoff to-dos, and one call per completed capture.
- Steps 4 and 6 of the skill need each capture's age (singletons are kept up to 7 days, and `dropped` items are kept another 7). The subagent guesses these ages, because the listing gives it no date math.
- `process-inbox all=True` (`tools_gtd_core.py`) already returns the inbox in a compact form, but it leaves out Today and has no age field.
- `reader.inbox()` and `reader.today()` exist, and the `Todo` model already carries `created` and `modified`.

## Goal
The intake sweep reads everything it needs from Things in one call, with ages computed by the server rather than guessed.

## Success criterion
- A nightly intake pass makes exactly one Things read call for the sweep (Inbox plus Today).
- Each item carries id, title, notes, tags, project/area, list, created date and age in days.
- Carded captures are closed in one `bulk-complete` call with `completion_notes` "Carded as COS-n".
- Drops are tagged in one `bulk-modify` call.
- The server returns facts only: no coaching text in the output.

## Appetite
5

## Out of scope
- Superhuman, Linear and WhatsApp sweeps.
- The clustering logic itself.
- Removing coaching prose from the other review tools (`prompts.py`, the delegate advice). That is its own card if wanted.
- Filtering out launcher "Run COS-n" to-dos or the Home Assistant project on the server. Those are casey-os rules, so the skill keeps them.

## Done artifact
A merged PR on CaseyRo/mcp-things (process-inbox `include_today`, plus age fields, with green tests), deployed on cc1. In casey-os, `skills/intake/SKILL.md` steps 1 and 6 name the calls.

## Verdict
Build.

Riskiest assumption: that the Things `created` date is a good stand-in for "first captured". A to-do moved from another list into Today keeps its original creation date, which is the age the intake actually wants, so the assumption is probably fine.

Cheapest test: compare `created` against the dates the 23 Nov intake (COS-272) assumed.

Things does not timestamp tags, so the clock for `dropped` items cannot be read from Things directly. The skill should write the drop date into the note, as "Dropped 23 Nov 2026".
