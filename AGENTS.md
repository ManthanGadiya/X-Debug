# AGENTS.md

# XDebug Development Agent Guide

**Project:** XDebug — Explainable AI Debugging Assistant

**Purpose:** This document defines the expected behavior of any autonomous coding agent contributing to XDebug. The goal is to ensure every contribution is high quality, well documented, testable, and aligned with the project's long-term vision.

---

# Mission

Your responsibility is **not** to generate code.

Your responsibility is to engineer XDebug like a senior software engineer.

Every decision should move the project closer to becoming an Explainable Software Intelligence Platform.

Always optimize for:

* Correctness
* Maintainability
* Modularity
* Scalability
* Explainability
* Testability

Never optimize for "quick hacks."

---

# Primary Objective

Complete the project from planning to Version 1 release.

Do not stop after implementing one feature.

Always determine what should be done next.

When one task finishes:

* update documentation if needed
* commit meaningful work
* determine the next logical milestone
* continue implementation

Remain in the development loop until there are blockers requiring human input.

---

# Source of Truth

Before implementing anything, read the documentation.

Read the documents in approximately this order:

1. docs/prd.md
2. docs/architecture.md
3. docs/analysis-pipeline.md
4. docs/xai-methodology.md
5. docs/bug-localization.md
6. docs/database.md (when available)
7. docs/api-spec.md (when available)
8. docs/roadmap.md
9. docs/research.md (future)

Implementation must follow these documents.

Never contradict them.

If documentation conflicts:

Stop and ask the user.

---

# Documentation Rule

Documentation drives implementation.

Never invent architecture.

If required information is missing:

Ask the user.

Do not guess.

---

# Project Status Tracking

The README should remain stable.

Only one section may be updated continuously:

## Current Status

Update this section after meaningful milestones.

Include:

* completed modules
* current milestone
* current branch
* latest completed feature
* next milestone
* quick start instructions (only when they change)

Do not rewrite other README sections unless explicitly requested.

---

# Development Workflow

Every task follows this lifecycle.

Research

↓

Design

↓

Implementation

↓

Unit Tests

↓

Integration Tests

↓

Documentation

↓

Static Analysis

↓

Commit

↓

Push

↓

Continue

Skipping steps is not allowed.

---

# Git Workflow

Never work directly on `main`.

Always create feature branches.

Examples

```text
feature/ast-parser
feature/call-graph
feature/runtime-engine
feature/frontend-dashboard
feature/bug-localization
feature/api-layer
```

Bug fixes

```text
fix/runtime-crash
```

Documentation

```text
docs/prd-update
```

Research

```text
research/confidence-engine
```

---

# Commit Strategy

Commit after every meaningful milestone.
You don't need to commit everything at once.
Commit often, without being like a beginner.

Avoid massive commits.

Good examples

```text
feat(ast): implement Python AST parser

feat(graph): add dependency graph builder

feat(runtime): capture execution traces

feat(localization): implement candidate ranking

feat(api): add repository upload endpoint

feat(frontend): integrate graph visualization

refactor(parser): simplify parser interface

fix(cfg): resolve incorrect branch traversal

test(runtime): add execution trace coverage

docs(architecture): update pipeline diagram
```

Bad examples

```text
update

changes

work

fix

commit
```

Every commit should represent a logical unit of work.

---

# Push Philosophy

Every completed feature should be merge-ready.

Before merging verify:

* builds successfully
* tests pass
* documentation updated
* no dead code
* lint passes

**push after the branch is finished**
---

# Engineering Principles

Always prefer

Small modules

↓

Clear interfaces

↓

Loose coupling

↓

High cohesion

Never create monolithic classes.

---

# Architecture Rules

Respect the layered architecture.

Frontend

↓

API

↓

Services

↓

Analysis

↓

Graph Engine

↓

Storage

No shortcuts.

---

# Code Quality

Backend

* Python type hints
* docstrings
* Ruff
* Black
* Pytest

Frontend

* TypeScript
* ESLint
* Prettier

General

* meaningful names
* no duplicated logic
* no unused code
* dependency injection where appropriate

---

# Testing Requirements

Every new feature requires tests.

Prefer

Unit Tests

↓

Integration Tests

↓

End-to-End Tests

Every discovered bug becomes a regression test.

---

# Tool Usage

Use tools when they materially improve implementation quality.

## Required Skills

Before beginning major work, use:

* caveman
* ponytail
* find-skill

Use **find-skill** to discover additional specialized skills that improve implementation quality.

Only install or use skills that directly benefit the current task.

---

# MCP Usage

Use MCPs whenever appropriate.

Preferred MCPs

* Agent Memory
* Firecrawl
* Hermes
* MarkItDown
* Reticle
* Ruflo

Guidelines

Agent Memory

* remember implementation decisions
* retrieve previous design context

Firecrawl

* official documentation
* specifications
* language references

Hermes

* planning
* task decomposition
* long-running execution

MarkItDown

* documentation processing
* markdown transformation

Reticle

* repository understanding
* structural analysis

Ruflo

* code quality
* formatting
* lint-related assistance

Do not use MCPs unnecessarily.

Choose the appropriate tool for the task.

---

# Research First

Before implementing unfamiliar components:

Research

↓

Compare alternatives

↓

Choose architecture

↓

Implement

Do not implement the first idea blindly.

---

# Documentation During Development

Whenever a significant architectural decision changes:

Update the relevant documentation.

Avoid documentation drift.

---

# Current Milestone Logic

Always determine:

Current milestone

↓

Remaining tasks

↓

Dependencies

↓

Best next task

↓

Continue

Never wait for explicit instructions unless blocked.

---

# Blocking Conditions

Pause and ask the user only if:

* documentation is missing
* requirements conflict
* architectural ambiguity exists
* multiple valid approaches require product decisions
* security-sensitive decisions require approval

Otherwise continue autonomously.

---

# Performance Philosophy

Optimize only after correctness.

Priority

Correctness

↓

Reliability

↓

Maintainability

↓

Performance

↓

Micro-optimizations

---

# Security

Never execute repositories directly on the host.

Use isolated execution.

Prefer

Docker

Future

Sandbox

Resource limits

Network restrictions

Timeouts

---

# Logging

Every subsystem should emit structured logs.

Include

* timestamps
* module
* operation
* duration
* result
* error context

Avoid print statements.

---

# Error Handling

Return structured errors.

Do not swallow exceptions.

Recover where possible.

Prefer partial analysis over total failure.

---

# Explainability

Every decision produced by XDebug should be explainable.

Avoid hidden heuristics.

Prefer deterministic reasoning.

---

# Continuous Improvement

During implementation continuously identify:

* duplicated code
* architectural improvements
* missing tests
* missing documentation
* opportunities for refactoring

Implement improvements when appropriate.

---

# Completion Definition

A feature is complete only when:

* implementation finished
* tests written
* documentation updated
* lint passes
* build passes
* committed
* merged into the active development branch

---

# Communication Style

When reporting progress:

State

* completed work
* current milestone
* next milestone
* blockers

Be concise.

Do not provide unnecessary commentary.

---

# Final Principle

Build XDebug as if it will become the reference implementation for explainable software debugging.

Every line of code should make the system easier to understand, easier to extend, and easier to trust.

If required information is unavailable, consult the project documentation first.

If the answer still cannot be determined, stop and ask the user rather than making unsupported assumptions.
