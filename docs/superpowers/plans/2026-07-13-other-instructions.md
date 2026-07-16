# Other Instructions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional `other_instructions` under likes/dislikes (web + mobile, with mobile likes/dislikes) and inject it as a hard chef constraint.

**Architecture:** Same discovery → profile → planner prompt path as likes/dislikes; store as a plain string; prompt-only hard rules (allergies/safety override only).

**Tech Stack:** TypeScript (app-core, web, mobile), Pydantic/Python (API, shared models, agent, meal_planner)

---

### Task 1: Shared types & API/domain models

**Files:**
- Modify: `packages/app-core/src/types.ts`
- Modify: `apps/api/src/meal_agent_api/schemas.py`
- Modify: `packages/shared/src/shared/models.py`
- Modify: `packages/agent/src/agent/conversation.py`
- Modify: `apps/web/src/App.tsx` (local `profileToAnswers`)

- [ ] Add `other_instructions: string` / `str = ""` everywhere defaults and converters map it (string, not split_list)
- [ ] Optional CLI question after dislikes

### Task 2: Planner prompt

**Files:**
- Modify: `packages/meal_planner/src/meal_planner/planner.py`

- [ ] Add `other_instructions` + hard `other_instructions_rules` to `_build_prompt` constraints
- [ ] Clarify `chef_notes` should acknowledge applied instructions when present

### Task 3: Web + mobile UI

**Files:**
- Modify: `apps/web/src/steps/DiscoveryStep.tsx`
- Modify: `apps/mobile/app/discovery.tsx`

- [ ] Web: textarea under likes/dislikes
- [ ] Mobile: likes, dislikes, other_instructions fields matching existing inputs

### Task 4: Verify

- [ ] Typecheck / quick sanity that defaults load and profile round-trip includes the field
