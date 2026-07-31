# 🐞 XDebug

> **Explainable AI Debugging Assistant**
> *Understand the software before attempting to fix it.*

---

## Current Status

* **Milestone:** Phase 4 — Runtime Analysis Engine (Test Execution) — released
* **Branch:** `main` (released from `develop`)
* **Completed:**
  * Backend foundation (FastAPI): config, structured logging, DI container, error envelopes, request middleware, health endpoint
  * Frontend foundation (React + Mantine + Vite): routing, theme, API client, dashboard home page with backend health check
  * Docker infrastructure: backend/frontend images + Compose with PostgreSQL and Neo4j
  * CI workflow (GitHub Actions): backend lint/format/typecheck/tests + frontend lint/typecheck/format/test/build
  * Repository ingestion: local zip upload, GitHub clone, language detection (Python/C/C++), ignore rules with `.gitignore` support, project loader producing a normalized repository representation (`POST /projects/upload`, `POST /projects/github`)
  * Static analysis engine: AST parsing for Python (stdlib `ast`) and C/C++ (tree-sitter), dependency graph, call graph, control flow graph, and data flow analysis, orchestrated by the analysis pipeline (`POST /analysis/start`, `GET /analysis/{id}`, `GET /analysis/{id}/graphs/{kind}`)
  * Runtime analysis engine: bounded subprocess execution with timeouts and output caps, Python tracing via `sys.settrace` (function execution order, call/return events, variable snapshots, exception and stack trace capture, execution timeline), C/C++ compile-and-run via the configured toolchain, entry-point detection per language (`POST /runtime/run`, `GET /runtime/{id}`, `GET /runtime/{id}/trace/{language}`)
  * Test execution: runs a project's available tests in bounded child processes — Python through pytest with a JUnit XML report (per-case outcomes and durations), C/C++ test mains compiled and executed with the configured toolchain, with per-language suites and results (`POST /tests/run`, `GET /tests/{id}`, `GET /tests/{id}/results/{language}`)
* **Next milestone:** Phase 4 completion — execution replay

Quick start:

**Requirements:** Python 3.12+, Node.js 24+, and Docker (optional, for the full stack).

### Backend

```sh
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows · macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The API runs at **http://localhost:8000** with interactive docs at **http://localhost:8000/docs**. No configuration is required — the backend boots with safe defaults and writes analysis artifacts under `backend/.xdebug-workspace`.

### Frontend

```sh
cd frontend
npm install
npm run dev
```

The dashboard runs at **http://localhost:5173** and connects to the backend automatically.

### Full stack with Docker

```sh
docker compose up --build
```

Starts the backend, frontend, PostgreSQL, and Neo4j together.

---

## 🚀 Overview

XDebug is an **Explainable Debugging Platform** that helps developers identify **where a bug originated, why it happened, how it propagated through the system, and how to fix it**.

Unlike traditional debuggers that stop at the crash location, or AI coding assistants that guess fixes from limited context, XDebug performs **whole-project program analysis** to reconstruct the complete chain of events leading to a software failure.

The goal is not to replace developers.

The goal is to **make debugging understandable, trustworthy, and significantly faster.**

---

## 🎯 The Problem

Modern debugging is still highly inefficient.

A typical workflow looks like this:

```text
Application crashes

↓

Read stack trace

↓

Search Google / StackOverflow

↓

Ask ChatGPT

↓

Apply suggested fix

↓

Another error appears

↓

Repeat
```

This process is slow because:

* The real bug is often far from the crash location.
* Large codebases exceed LLM context windows.
* AI assistants rarely understand the complete project architecture.
* Developers spend more time locating bugs than fixing them.

---

## 💡 Our Solution

XDebug analyzes the **entire software project** before attempting to explain the bug.

Instead of asking:

> "Where did the exception occur?"

XDebug asks:

> "What caused the exception to occur?"

It reconstructs the complete causal chain using:

* Static Analysis
* Runtime Analysis
* Graph Reasoning
* Evidence Fusion

and produces an explainable debugging report.

---

# ✨ Features

## ✅ Repository Analysis

* GitHub Repository Support
* Local Project Analysis
* Multi-language architecture
* Project understanding

---

## ✅ Static Analysis

* Abstract Syntax Tree (AST)
* Call Graph
* Dependency Graph
* Control Flow Graph (CFG)
* Data Flow Analysis
* Symbol Resolution
* Variable Tracking
* Unreachable Code Detection

---

## ✅ Runtime Analysis

* Execute projects
* Run tests
* Capture stack traces
* Record execution traces
* Track runtime variables
* Build execution timeline

---

## ✅ Bug Localization

Instead of reporting only where the program crashed,

XDebug identifies:

* Root Cause
* Error Propagation Path
* Responsible Variables
* Responsible Functions
* Responsible Files

---

## ✅ Explainable Reports

Every report answers:

* ✅ What happened?
* ✅ Where did it happen?
* ✅ Why did it happen?
* ✅ How did it propagate?
* ✅ What evidence supports this?
* ✅ What should be fixed?

---

## ✅ Visualization

Version 1 supports:

* Dependency Graph
* Call Graph
* Control Flow Graph
* Variable Flow
* File Relationship Graph

---

# 🏗 Architecture

```text
Repository

↓

Project Loader

↓

Parser

↓

AST

↓

Dependency Graph

↓

Call Graph

↓

Control Flow Graph

↓

Data Flow Analysis

↓

Runtime Analysis

↓

Evidence Graph

↓

Bug Localization

↓

Explanation Engine

↓

Visualization
```

---

# 🧠 Core Philosophy

Most debugging tools answer:

> "The error occurred here."

XDebug answers:

> "The failure appeared here, but the actual problem started over there."

Every explanation must satisfy four questions.

1. What happened?
2. Where did it originate?
3. Why did it happen?
4. How can it be fixed?

---

# 🔬 Explainability

Unlike traditional AI assistants,

XDebug does **not** rely on language models in Version 1.

Every explanation is derived from:

* Program Analysis
* Runtime Evidence
* Graph Traversal
* Causal Reasoning

Every conclusion can be traced back to concrete evidence.

No hallucinations.

No unsupported assumptions.

---

# 📊 Technology Stack

## Frontend

* React
* TypeScript
* Vite
* React Flow
* Cytoscape.js

---

## Backend

* FastAPI
* Python

---

## Static Analysis

* Python AST
* Tree-sitter
* libclang

---

## Runtime Analysis

* Python Trace API
* Runtime Instrumentation

---

## Graph Processing

* NetworkX
* Neo4j

---

## Storage

* PostgreSQL
* Neo4j

---

## Containerization

* Docker

---

# 📂 Repository Structure

```text
xdebug/

├── backend/
│
├── frontend/
│
├── parser/
│
├── analysis/
│   ├── ast/
│   ├── cfg/
│   ├── call_graph/
│   ├── dependency/
│   ├── data_flow/
│   └── runtime/
│
├── localization/
│
├── explanation/
│
├── visualization/
│
├── graph/
│
├── storage/
│
├── docs/
│
├── tests/
│
└── docker/
```

---

# 🚀 Development Roadmap

## Version 1

* Repository Analysis
* Static Analysis
* Runtime Analysis
* Bug Localization
* Explainable Reports
* Graph Visualization

---

## Version 2

* VS Code Extension
* CLI
* Incremental Analysis
* Graph Neural Networks
* Multi-language Support

---

## Version 3

* Hybrid Symbolic + LLM Reasoning
* Automatic Patch Generation
* Team Collaboration
* Distributed Debugging

---

# 🎯 Target Users

Primary

* Students
* Beginner Developers
* Interns
* Self-taught Programmers
* Vibe Coders

Secondary

* Professional Developers
* Open Source Contributors
* Engineering Teams

---

# 📈 Success Metrics

The project is evaluated using:

* Bug Localization Accuracy
* Precision
* Recall
* F1 Score
* Reduction in Debugging Time
* Explanation Quality

---

# 🔮 Future Vision

The long-term goal of XDebug is not to become another AI coding assistant.

It aims to become an **Explainable Software Intelligence Platform** capable of understanding software systems, reconstructing software behavior, localizing failures, and helping developers debug with confidence.

---

# 🤝 Contributing

Contributions are welcome.

Before contributing:

1. Read the documentation in the `docs/` directory.
2. Follow the project's coding standards.
3. Create a feature branch.
4. Write tests for new functionality.
5. Ensure all checks pass before opening a pull request.

---

# 📄 Documentation

Project documentation includes:

* Product Requirements Document
* System Architecture
* Analysis Pipeline
* XAI Methodology
* Bug Localization Methodology
* Database Design
* API Specification
* Development Roadmap

---

# 📜 License

This project is licensed under the MIT License.

See the `LICENSE` file for details.

---

# 🌟 Why XDebug?

Debugging is not about finding where software crashed.

Debugging is about understanding **why** software failed.

XDebug exists to make that understanding faster, clearer, and evidence-driven.

> **"Understand the software before attempting to fix it."**
