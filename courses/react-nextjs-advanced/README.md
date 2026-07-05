# Advanced React, Next.js & Browser Systems Engineering
### An Intern-to-Production Curriculum

**Instructor's note:** I've spent over three decades split between building distributed systems in production and teaching engineers how software actually works underneath the frameworks they use daily. The single biggest failure mode I see in junior frontend engineers is *framework fluency without systems literacy* — they can write a `useEffect`, but they can't explain why it fires twice, what a microtask is, or why their bundle is 400KB. This course exists to close that gap. Every chapter goes from "how do I use this" to "why does this exist, what does it cost, and what breaks if I'm wrong."

This is not a tutorial series. It is an engineering curriculum with a single capstone system you will build and rebuild in increasing sophistication across 30 chapters.

> **Status:** ✅ Complete — 30 chapters across Phases 1–7, sequenced in genuine pedagogical order (not just grouped by topic), starting from basic scaffolding setups for JS, TS, React, and Next.js. See the [Build Log](#build-log) at the bottom for history.

## How This Course Is Organized

```
courses/react-nextjs-advanced/
├── README.md                                  <- you are here
├── phase-1-browser-systems/                   <- Chapters 1-2
├── phase-2-html-css-styling/                  <- Chapters 3-4
├── phase-3-js-runtimes/                       <- Chapters 5-8
├── phase-4-typescript/                        <- Chapters 9-11
├── phase-5-react-architecture/                <- Chapters 12-23
├── phase-6-nextjs/                            <- Chapters 24-28
└── phase-7-production-quality/                <- Chapters 29-30
```

Each chapter file follows the same 15-section engineering template (including **Supplementary Topics & Core Lecture Knowledge** as Section 15) and ends with a **Capstone Integration Step** that advances the same running project: **ScribeCollab**.

### 🧭 How to read this course

**Chapters 1–30 are organized from basic browser rendering to production deployment.** Read them sequentially to build a continuous engineering foundation. Every chapter states what it builds on and what comes next.

---

## 🏷️ Skill Taxonomy & Difficulty Legend

| Tier | Meaning |
|---|---|
| **Level A — Foundational** | Zero prior framework assumptions. Mandatory for interns. |
| **Level B — Intermediate** | Architectural abstractions and pattern composition. |
| **Level C — Advanced** | Memory, concurrency, and performance diagnostics. |
| **Level D — Expert** | Enterprise orchestration, compiler internals, security threat modeling. |

**Domain flags:** `JS/Browser` (engine + Web APIs) · `TS` (static typing) · `React` (rendering engine) · `Next.js` (server/edge architecture)

---

## 🏗️ The Capstone: ScribeCollab

Every phase of this course builds a single production-grade application: **ScribeCollab** — a real-time, collaborative Markdown workspace with offline sync, role-based access control, and tuned rendering performance.

```
+-------------------------------------------------------------------+
| Presentation Layer (Next.js App Router, Tailwind, A11Y Semantic)  |
+-------------------------------------------------------------------+
                                  │
                                  ▼
+-------------------------------------------------------------------+
| App State & Sync (Zustand Stores, useSyncExternalStore, CRDTs)    |
+-------------------------------------------------------------------+
                                  │
                                  ▼
+-------------------------------------------------------------------+
| Client Storage & Threading (IndexedDB, Web Workers background)    |
+-------------------------------------------------------------------+
                                  │
                                  ▼
+-------------------------------------------------------------------+
| Network / Security Barrier (Edge Middleware, Server Actions, CSP) |
+-------------------------------------------------------------------+
```

Each chapter's **Capstone Integration Step** shows exactly how that chapter's theory extends this system.

---

## 📚 Full Curriculum Map

### Phase 1 — Browser Systems & DOM Orchestration
| # | Chapter | Level | File |
|---|---|---|---|
| 1 | Semantic HTML, Accessibility & Basic Browser Rendering | A | [chapter-01](./phase-1-browser-systems/chapter-01-semantic-html-a11y.md) |
| 2 | Browser Web APIs, DOM Orchestration & I/O | C | [chapter-02](./phase-1-browser-systems/chapter-02-web-apis-dom.md) |

### Phase 2 — HTML & CSS, Styling & Animation Systems
| # | Chapter | Level | File |
|---|---|---|---|
| 3 | CSS Architecture, Responsive Design & Styling Systems | A→C | [chapter-03](./phase-2-html-css-styling/chapter-03-css-styling-architecture.md) |
| 4 | Animation Systems & Framer Motion | B | [chapter-04](./phase-2-html-css-styling/chapter-04-animations-framer-motion.md) |

### Phase 3 — JavaScript Runtimes (ES6+ & Engine Details)
| # | Chapter | Level | File |
|---|---|---|---|
| 5 | JavaScript Runtime — Scaffolding & Syntax Foundations | A | [chapter-05](./phase-3-js-runtimes/chapter-05-js-environment-setup-syntax.md) |
| 6 | JS Runtime: Execution Context, Scope & Closures | B | [chapter-06](./phase-3-js-runtimes/chapter-06-execution-context-closures.md) |
| 7 | The JS Memory Model & Object References | B | [chapter-07](./phase-3-js-runtimes/chapter-07-memory-model-references.md) |
| 8 | JS Asynchronous Runtime & The Event Loop | C | [chapter-08](./phase-3-js-runtimes/chapter-08-event-loop-async.md) |

### Phase 4 — TypeScript & Static Type Systems
| # | Chapter | Level | File |
|---|---|---|---|
| 9 | TypeScript — Environment Scaffolding & Compiler Architecture | A | [chapter-09](./phase-4-typescript/chapter-09-typescript-scaffolding-compilation.md) |
| 10 | TypeScript Foundations & Modern Build Tooling | A | [chapter-10](./phase-4-typescript/chapter-10-typescript-foundations.md) |
| 11 | Advanced TypeScript & Runtime Validation | C | [chapter-11](./phase-4-typescript/chapter-11-advanced-typescript.md) |

### Phase 5 — React System Architecture & Hooks
| # | Chapter | Level | File |
|---|---|---|---|
| 12 | React — Application Scaffolding & Project Tooling | A | [chapter-12](./phase-5-react-architecture/chapter-12-react-scaffolding-vite-build-process.md) |
| 13 | React Philosophy & Component Composition | A | [chapter-13](./phase-5-react-architecture/chapter-13-react-philosophy-composition.md) |
| 14 | Core React Hooks & State Orchestration | B | [chapter-14](./phase-5-react-architecture/chapter-14-core-hooks.md) |
| 15 | Refs Deep-Dive, Imperative APIs & Legacy Class Components | B/C | [chapter-15](./phase-5-react-architecture/chapter-15-refs-imperative-legacy-class-components.md) |
| 16 | Debugging, Strict Mode & Developer Tools | B | [chapter-16](./phase-5-react-architecture/chapter-16-debugging-devtools-strict-mode.md) |
| 17 | React Rendering Internals & Concurrent Mode | C | [chapter-17](./phase-5-react-architecture/chapter-17-rendering-internals-concurrent.md) |
| 18 | Advanced Forms, Validation & Store Architectures | B/C | [chapter-18](./phase-5-react-architecture/chapter-18-forms-validation-stores.md) |
| 19 | Modern Form Actions: `useActionState`, `useFormStatus` & `useOptimistic` | C | [chapter-19](./phase-5-react-architecture/chapter-19-modern-form-actions-optimistic-ui.md) |
| 20 | Error Handling, Suspense & List Virtualization | C | [chapter-20](./phase-5-react-architecture/chapter-20-error-handling-suspense-virtualization.md) |
| 21 | Client-Side Routing with React Router | B/C | [chapter-21](./phase-5-react-architecture/chapter-21-client-side-routing-react-router.md) |
| 22 | State Management Ecosystem: Redux Toolkit & TanStack Query | C | [chapter-22](./phase-5-react-architecture/chapter-22-state-ecosystem-redux-tanstack-query.md) |
| 23 | Advanced Component Design Patterns | B/C | [chapter-23](./phase-5-react-architecture/chapter-23-advanced-component-patterns.md) |

### Phase 6 — Next.js Enterprise Orchestration
| # | Chapter | Level | File |
|---|---|---|---|
| 24 | Next.js — Enterprise Project Scaffolding & App Router | A | [chapter-24](./phase-6-nextjs/chapter-24-nextjs-scaffolding-routing-basics.md) |
| 25 | Next.js Layout Architecture, Navigation & A11Y | A | [chapter-25](./phase-6-nextjs/chapter-25-layout-navigation-a11y.md) |
| 26 | Next.js Rendering Strategies & Server Architecture | C | [chapter-26](./phase-6-nextjs/chapter-26-rendering-strategies-server.md) |
| 27 | APIs, Middleware & Modern Security Shields | C/D | [chapter-27](./phase-6-nextjs/chapter-27-apis-middleware-security.md) |
| 28 | Enterprise Auth, Deployment & Performance Auditing | D | [chapter-28](./phase-6-nextjs/chapter-28-auth-deployment-performance.md) |

### Phase 7 — Production Quality, Performance & Testing
| # | Chapter | Level | File |
|---|---|---|---|
| 29 | Testing Strategy: Unit, Component & End-to-End Testing | B/C | [chapter-29](./phase-7-production-quality/chapter-29-testing-strategy.md) |
| 30 | CI/CD Pipelines & Production Observability | D | [chapter-30](./phase-7-production-quality/chapter-30-cicd-observability.md) |

---

## 🛠️ Lesson Template

Every chapter file adheres to this structure without exception:

1. **Learning Objectives** — Bloom's Taxonomy verbs, measurable outcomes.
2. **Motivation** — the real-world cost of not knowing this.
3. **Core Theory** — execution paths, systems diagrams, mental models.
4. **Visual Diagrams** — Mermaid diagrams of execution flow.
5. **Step-by-Step Walkthroughs** — exact interaction timelines.
6. **Internal Implementation** — how the engine/framework does this under the hood.
7. **Code Examples** — minimal → practical → production-ready → anti-pattern/corrected (→ bonus additional example).
8. **Common Mistakes** — Junior / Mid-level / Senior-production traps.
9. **Performance Analysis** — time complexity, memory, frame budget.
10. **Security Inventory** — vulnerabilities and mitigations.
11. **Technology Comparisons** — objective alternative-tool tables.
12. **Engineering Decisions** — business/maintenance trade-offs.
13. **Exercises** — Easy / Medium / Hard.
14. **Capstone Integration Step** — advances ScribeCollab.
15. **Supplementary Topics & Core Lecture Knowledge** — Maps and details corresponding syllabus content from `supplement.txt`.

---

## 🧭 Capstone Assessment Rubric

| Dimension | Poor (Intern) | Meets Criteria (Mid) | Exceptional (Lead Architect) |
|---|---|---|---|
| **A11Y Integration** | No ARIA, keyboard traps present | Correct semantics, working modal focus | Full A11Y tree compliance, live-region sync announcements |
| **Type Safety** | Pervasive `any`, no schemas | Clean generics, type-checking passes | Branded types, recursive conditionals, zero assertions |
| **Render Tuning** | Full-page re-renders on keystroke | Stable keys, basic caching | Sub-5ms concurrent typing, selector-based store caching |
| **Security Shielding** | Unescaped script rendering | Sanitized inputs, correct CORS | Strict CSP, branded-type enforced data paths |

## 📖 Core System Glossary

- **Mechanical Sympathy** — programming with an understanding of how the underlying hardware, engine, or compiler actually executes your code.
- **Execution Context** — the JS engine's wrapper for scope, prototype chain, and `this` binding during code execution.
- **Fiber** — React's internal unit-of-work object enabling interruptible, non-recursive rendering.
- **Hydration Mismatch** — divergence between server-rendered HTML and the client's initial virtual DOM.
- **Tearing** — visual inconsistency where different DOM parts reflect different values of the same state in one paint.
- **Branded Type** — a compile-time nominal-typing technique that forces explicit validation before a value can flow into a sensitive boundary.

## Build Log

- ✅ **Course Reorganization & Supplement Integration** — Restructured core chapters into 7 sequential phases matching the exact chronological learning progression: `browser -> html, css -> js -> typescript -> react -> nextJs -> production`.
- ✅ **Basic Scaffolding & Setup Modules** — Integrated 4 new core scaffolding chapters at the beginning of the JS, TS, React, and Next.js sections (Chapters 5, 9, 12, and 24) to provide a complete, clean-setup curriculum from scratch. Renumbered the entire course into a 30-chapter curriculum.
- 🎓 **30-Chapter Systems Course Complete.** Structured sequentially, single ScribeCollab capstone thread.
