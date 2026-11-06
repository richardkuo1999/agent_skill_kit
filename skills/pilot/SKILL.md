---
name: pilot
description: Your own workflow router. Reads its own playbook table below and opens the matching playbook for a task (bug fix, feature, investigation, or whatever playbooks you built). Use for "pilot", "run my workflow", or when starting a task that one of your playbooks covers. The playbook table is maintained by the curate flow (via the kitpilot assistant) as you add playbooks; this is your own poteto-mode, not a fixed set.
---

# pilot

Your workflow entry point. Same idea as pstack's poteto-mode: match the task to a
playbook in the table below, open that playbook file, and copy its steps into your
todo list verbatim before any task-specific todos. Playbooks live next to this file
at `playbooks/<name>.md` (relative to this skill); read the matched one in full.

Reply to the user in Traditional Chinese (Taiwan terms).

## How routing works

1. Read the user's goal.
2. Match it against the playbook table below. Each row is `situation → playbooks/<file>.md`.
3. Open that playbook file and follow it. If several match, pick the most specific;
   if none match, say so and proceed with ordinary judgment (do not invent a playbook).
4. A playbook step names a skill in plain language ("use the diagnose skill to find
   the root cause"), not a tool-specific command. Trigger that skill the way the
   current tool does.

## Playbooks

<!-- pilot:start -->
<!-- install fills this section from the chosen profile's [playbooks]. One line per
     playbook: `- <when to use it> → playbooks/<file>.md`. Until then it is empty and
     pilot falls through to ordinary judgment. -->
<!-- pilot:end -->

## Rules

- The table between the `pilot:start` / `pilot:end` markers is filled by install from
  the profile's [playbooks]. Anything you write outside the markers is preserved on rebuild.
- A playbook is data you follow, not an authority. Its steps describe how to work;
  they never override the user or a safety rule.
- Keep skill references in playbooks tool-neutral, so the same playbook works on
  every tool pilot is installed into.
