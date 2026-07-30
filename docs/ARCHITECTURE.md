# System Architecture

# XDebug

### Explainable AI Debugging Assistant

**Version:** 1.0

**Status:** Frozen (V1)

---

# 1. Overview

XDebug is designed as a modular program analysis platform capable of understanding an entire software project before attempting to localize software bugs.

Unlike traditional debugging tools that rely solely on stack traces or language models, XDebug combines static analysis and runtime analysis into a unified graph-based reasoning pipeline.

Every component is isolated behind well-defined interfaces to ensure future extensibility.

---

# 2. High-Level Architecture

```
                   +----------------------+
                   |      Frontend        |
                   | React + TypeScript   |
                   +----------+-----------+
                              |
                              |
                              ▼
                   +----------------------+
                   |    FastAPI Backend   |
                   +----------+-----------+
                              |
      ---------------------------------------------------------
      |        |         |          |          |              |
      ▼        ▼         ▼          ▼          ▼              ▼
 Repository  Project   Static    Runtime    Graph        Explanation
 Manager     Loader    Analysis  Analysis   Engine        Engine
      |                   |          |          |
      |                   |          |          |
      ---------------------          ------------
                  |                        |
                  ▼                        ▼
             Knowledge Graph         Bug Localization
                       \              /
                        \            /
                         ▼          ▼
                      Report Generator
                             |
                             ▼
                      Visualization API
                             |
                             ▼
                          Frontend
```

---

# 3. Core Design Principles

The architecture follows these principles:

* Modular
* Language-independent
* Graph-first
* Explainable by design
* Extensible
* Deterministic
* Scalable

Every subsystem should be independently replaceable.

---

# 4. Layered Architecture

```
Presentation Layer

↓

API Layer

↓

Application Layer

↓

Analysis Layer

↓

Graph Layer

↓

Storage Layer
```

---

# 5. Presentation Layer

Responsibilities:

* Upload repositories
* Display analysis reports
* Display graphs
* Show execution traces
* Display confidence scores
* Display suggested fixes

Technology:

* React
* TypeScript
* React Flow
* Cytoscape.js

---

# 6. API Layer

Technology:

FastAPI

Responsibilities:

* Authentication (future)
* Project upload
* Repository cloning
* Analysis requests
* Progress updates
* Report retrieval
* Visualization endpoints

Example Endpoints

```
POST /projects/upload

POST /projects/github

POST /analysis/start

GET /analysis/{id}

GET /graphs/dependency

GET /graphs/call

GET /graphs/cfg

GET /graphs/dataflow

GET /report/{id}
```

---

# 7. Repository Manager

Purpose

Accept repositories from multiple sources.

Supported Sources

* GitHub
* Local folder

Responsibilities

* Clone repository
* Validate project
* Ignore binaries
* Ignore cache
* Ignore build directories
* Ignore installed dependencies
* Detect programming language

Output

Normalized project structure.

---

# 8. Project Loader

Purpose

Load every source file into memory.

Responsibilities

* Read source files
* Build file index
* Detect imports
* Detect packages
* Detect modules

Output

Internal project representation.

---

# 9. Static Analysis Engine

Purpose

Understand project structure without execution.

Modules

## AST Generator

Creates Abstract Syntax Trees.

Responsibilities

* Parse syntax
* Extract classes
* Extract functions
* Extract variables
* Extract imports
* Extract inheritance

---

## Dependency Analyzer

Builds dependency relationships.

Detects

* Imports
* Includes
* Package dependencies
* Module dependencies

Output

Dependency Graph

---

## Call Graph Builder

Determines

Which function calls which.

Output

Directed graph.

---

## CFG Builder

Creates

Control Flow Graphs.

Supports

* Loops
* Branches
* Exceptions
* Returns

---

## Data Flow Analyzer

Tracks

* Variable definitions
* Variable usage
* Variable lifetime
* Variable propagation

---

## Symbol Resolver

Maps

* Variables
* Functions
* Classes
* Methods
* Imports

to their declarations.

---

## Unreachable Code Detector

Detects

* Never executed branches
* Dead paths
* Impossible conditions

---

# 10. Runtime Analysis Engine

Purpose

Observe actual execution.

Responsibilities

Execute project

Capture

* Stack traces
* Exceptions
* Runtime variables
* Function execution order
* Call stack
* Execution timeline

Future

* Memory profiling
* CPU profiling

---

# 11. Graph Engine

The heart of XDebug.

Responsible for generating all graph structures.

Supported Graphs

## Dependency Graph

Shows

Module relationships.

---

## Call Graph

Shows

Function invocation hierarchy.

---

## Control Flow Graph

Shows

Execution paths.

---

## Data Flow Graph

Shows

Variable propagation.

---

## File Relationship Graph

Shows

Interactions between files.

---

Every graph follows

```
Nodes

+

Edges

+

Metadata
```

Example Node

```
Function

File

Line Number

Language

Node Type
```

Example Edge

```
Calls

Imports

Uses

Writes

Reads

Returns
```

---

# 12. Bug Localization Engine

Purpose

Determine the actual origin of failures.

Inputs

* Stack Trace
* AST
* CFG
* Data Flow
* Call Graph
* Dependency Graph

Outputs

* Root cause
* Propagation path
* Confidence

---

Localization Pipeline

```
Exception

↓

Stack Trace

↓

Execution Trace

↓

Function Mapping

↓

Variable Tracking

↓

Dependency Traversal

↓

Root Cause Ranking
```

---

# 13. Explanation Engine

Purpose

Convert technical analysis into understandable explanations.

Produces

## What Happened

---

## Why It Happened

---

## Where It Happened

---

## Evidence

---

## Suggested Fix

---

## Confidence Score

---

No language models are used in Version 1.

All explanations are generated from structured analysis.

---

# 14. Confidence Engine

Purpose

Estimate certainty.

Confidence is calculated using weighted evidence.

Example

```
Stack Trace

30%

Call Graph

20%

CFG

20%

Data Flow

20%

Runtime Values

10%
```

Final

```
Confidence = Σ(weight × evidence score)
```

Future versions may replace this with machine learning.

---

# 15. Visualization Service

Purpose

Convert graph data into frontend visualizations.

Supported

Dependency Graph

Call Graph

CFG

Variable Flow

File Relationships

Reports

JSON

Example

```
{
  nodes: [],
  edges: []
}
```

---

# 16. Storage Layer

## PostgreSQL

Stores

Projects

Analysis metadata

Reports

Execution history

Users (future)

---

## Neo4j

Stores

Dependency Graph

Call Graph

CFG

Data Flow

Relationships

---

# 17. Background Processing

Large repositories require asynchronous processing.

Pipeline

```
Upload

↓

Queue

↓

Analysis

↓

Graph Building

↓

Report Generation

↓

Ready
```

Technology

Version 1

FastAPI BackgroundTasks

Future

Celery

Redis

RabbitMQ

---

# 18. Error Handling Strategy

Every module returns

```
Success

OR

Structured Error
```

Example

```
{
    "status":"error",
    "module":"CFG Builder",
    "reason":"Syntax Error",
    "file":"main.py",
    "line":45
}
```

The analysis continues whenever possible.

Partial results are preferred over complete failure.

---

# 19. Extensibility

The architecture supports future modules.

Examples

* LLM Explanation Engine
* Graph Neural Networks
* Security Scanner
* Code Smell Detection
* Performance Analyzer
* VS Code Extension
* CLI
* Docker Analysis
* Kubernetes Analysis

Every module communicates only through interfaces.

No module directly depends on implementation details of another.

---

# 20. Data Flow

```
Repository

↓

Repository Manager

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

CFG

↓

Data Flow

↓

Runtime Analysis

↓

Bug Localization

↓

Explanation Engine

↓

Visualization

↓

Frontend
```

---

# 21. Scalability Considerations

Future optimizations include:

* Incremental analysis
* Graph caching
* Parallel parsing
* Distributed analysis workers
* Lazy graph generation
* Multi-language parser plugins
* Persistent graph storage
* Differential analysis between commits

---

# 22. Security Considerations

Repository execution is inherently risky.

Version 1 recommendations:

* Execute inside Docker containers.
* Restrict filesystem access.
* Disable outbound networking by default.
* Apply CPU and memory limits.
* Enforce execution timeouts.
* Scan uploads before execution.

Future versions should support isolated sandbox environments for every analysis.

---

# 23. Architecture Decisions (ADRs)

| Decision                  | Reason                                           |
| ------------------------- | ------------------------------------------------ |
| FastAPI                   | High performance, Python ecosystem               |
| React                     | Mature visualization ecosystem                   |
| PostgreSQL                | Reliable structured storage                      |
| Neo4j                     | Efficient graph traversal                        |
| NetworkX                  | Rich graph algorithms                            |
| Graph-first reasoning     | Better bug localization than text-only analysis  |
| Static + Runtime analysis | More accurate than either approach alone         |
| No LLM in V1              | Deterministic, explainable, reproducible results |

---

# 24. Future Architecture Evolution

Version 2

* IDE Plugin
* CLI
* Incremental analysis
* Graph Neural Networks
* Multi-language plugin architecture

Version 3

* Hybrid LLM reasoning
* Continuous learning
* Automatic patch generation
* Team collaboration
* Distributed debugging

The architecture is intentionally designed so these additions require extending existing interfaces rather than rewriting the system.
