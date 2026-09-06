# 🤖 Universal AGENTS.md

Mandatory architectural guidelines and execution rules for AI coding assistants.

---

## 🤝 1. Collaboration & Workflow Discipline

1. **Proactive Clarifying Questions**: Steven's conceptual designs evolve during development. **Always ask insightful clarifying questions** to nail down requirements, edge cases, and architectural constraints.
2. **Git Branch & Release Flow**:
   - All new features and refactors start on a **fresh feature branch** off `develop`.
   - `develop` serves as the active integration branch before production release on `main`.
   - Create **atomic Conventional Commits** (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
   - Features must culminate in a PR passing all 4-stage CI quality gates before merging.
3. **Container Immutability**:
   - **NEVER** edit files or hot-patch code inside live running containers.
   - Always build/pull official images or rebuild via standard compose commands (`docker compose up -d --build`).

---

## 🏛️ 2. Core Code & Architectural Discipline

1. **SOLID & Single Responsibility**: Decompose files and classes exceeding **500 lines of code** into partial classes or focused sub-services.
2. **Interfaces by Default**: Build client-focused interfaces (`I*` in C#) even for single implementations to ensure loose coupling and testability.
3. **DRY vs YAGNI**:
   - **Rule of Three**: Duplication is acceptable across 2 instances; abstract on the 3rd occurrence.
   - Do not invent speculative multi-tier frameworks (YAGNI).
4. **Semantic Naming**:
   - **Banned**: `*Manager`, `*Helper`, `*Util`, `*Data` junk drawers.
   - **Enforced**: Role/action-based names (`DatabaseSeederService`, `UserAuthenticator`, `ServerStatusCard`, `use*Store.ts`).
5. **Efficiency**:
   - **Database**: If an operation requires 3+ database round-trips or complex multi-table joins, consolidate into a single **Stored Procedure** (`.sql` file) or multi-result query.
   - **Frontend**: Mandatory **granular Zustand selectors** (`useServerStore(s => s.servers.length)`) to prevent render cascades.
6. **Error Handling & Diagnostics**:
   - Never leak raw stack traces to API clients.
   - Capture rich debug logs with the exact inputs and state that caused the error.

---

## 💻 3. Polyglot Language Matrix

- **C# (.NET 9)**: `.slnx`, `System.CommandLine`, full DI, Dapper + Stored Procs (separate `.sql` files), SQLite WAL (MySQL-compatible) / MSSQL, native C# UIs (WPF/WinForms/Avalonia, no Electron), full `CancellationToken` propagation.
- **Python (3.12+)**: `uv`, `pyproject.toml`, FastAPI + FastMCP, Pydantic v2 schemas, `asyncio`, `pytest` ($\ge$ 80% coverage), `ruff`.
- **TypeScript / React**: React + TS strict + Vite, Zustand domain stores, pure CSS Modules + custom properties, bespoke components, `playwright-layout-inspector` 4-point audit.
- **C++ (C++20/23)**: MSBuild (Win) / CMake (Linux), `vcpkg`, strict RAII, smart pointers, GoogleTest (`gtest`), ASan/UBSan, Benchmark, C# `[LibraryImport]` / Python `pybind11` interop.

---

## 🧪 4. Testing & Agent Verification Protocol

1. **Test Harnesses**: Build closed-loop simulation harnesses with high-volume testing loops whenever crossing API/network boundaries or building tunable algorithms.
2. **Coverage**: Maintain $\ge$ 80% code coverage across unit, integration, and E2E suites.
3. **UI Layout Inspection**: Frontends must pass the 4-point `playwright-layout-inspector` audit (no overflow, mobile fit, $\ge$ 24px targets, $\ge$ 85 score) with `data-testid` attributes.
4. **6-Part Agent Feedback Envelope**: Format harness/test failures with `inputs`, `assumptions`, `active_settings`, `action_history`, `output_delta`, `captured_logs`, and `reproduction_command`.
5. **Empirical Verification**: Never claim a task complete without running build, tests, verifying logs, and probing `/health`.
