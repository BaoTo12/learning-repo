# **Master Course Specification: Advanced React, Next.js, and Browser Systems Engineering**

This document serves as the master specification, structural blueprint, and curriculum mapping for the downstream AI Content Generation Agent. The downstream agent must use this blueprint to generate complete, production-grade, highly comprehensive academic chapters.

## **🏷️ SKILL TAXONOMY & DIFFICULTY LEGEND**

The downstream content generator must use these tags to align the technical complexity and verification boundaries of each topic:

* **Difficulty Tiers:**  
  * **Level A (Foundational):** Crucial syntactic and runtime baselines. Essential for interns. Must contain zero assumptions of prior framework knowledge.  
  * **Level B (Intermediate):** Architectural abstractions, pattern compositions, and structural logic.  
  * **Level C (Advanced):** Low-level memory, concurrent execution, system validation boundaries, and performance diagnostics.  
  * **Level D (Expert):** Enterprise orchestration, compiler bypass structures, edge architectures, and security threat mitigation.  
* **Domain Flags:**  
  * **JS / Browser:** Core JavaScript engines (V8), Web APIs, and document lifecycles.  
  * **TS:** Static typing compile-time declarations, compiler behaviors, and validation boundaries.  
  * **React:** Rendering lifecycles, hooks, Fiber tree mutations, and scheduler priorities.  
  * **Next.js:** Server-side streaming engines, build setups, caching networks, and middleware pipelines.

## **🏗️ CORE CAPSTONE PROJECT: "ScribeCollab"**

To unify all chapters into an integrated system, students will build a single, cohesive production-grade application across the entire course: **ScribeCollab (A Real-Time, Collaborative Markdown Workspace with Offline Sync, Secure Role-Based Access Controls, and Advanced Render Tuning).**

                  \[ScribeCollab Multi-Layer Architecture\]  
                    
  \+-------------------------------------------------------------------+  
  | Presentation Layer (Next.js App Router, Tailwind, A11Y Semantic)  |  
  \+-------------------------------------------------------------------+  
                                    │  
                                    ▼  
  \+-------------------------------------------------------------------+  
  | App State & Sync (Zustand Stores, useSyncExternalStore, CRDTs)   |  
  \+-------------------------------------------------------------------+  
                                    │  
                                    ▼  
  \+-------------------------------------------------------------------+  
  | Client Storage & Threading (IndexedDB, Web Workers background)    |  
  \+-------------------------------------------------------------------+  
                                    │  
                                    ▼  
  \+-------------------------------------------------------------------+  
  | Network / Security Barrier (Edge Middleware, Next.js Actions, CSP)|  
  \+-------------------------------------------------------------------+

Each chapter contains a dedicated **Capstone Integration Step** showing how that chapter's theory modifies the workspace system.

## **📚 COMPLETE CURRICULUM & LEARNING OUTCOMES**

### **PHASE 1: JAVASCRIPT & BROWSER FUNDAMENTALS (INTERN BASELINE)**

#### **Chapter 1: Semantic HTML, Accessibility (A11Y), and Basic Browser Rendering**

* **Prerequisites:** None.  
* **Difficulty:** Level A (JS / Browser)  
* **Core Curriculum Topics:**  
  * **Semantic HTML Markup:** Structural layout nodes (\<main\>, \<header\>, \<nav\>, \<article\>, \<section\>, \<aside\>, \<footer\>) vs. generic divs.  
  * **Accessibility (A11Y) Core:** The Accessible Rich Internet Applications (ARIA) specification. Semantic landmarks, ARIA states, roles, and properties.  
  * **Focus Management & Keyboard Navigation:** Tab index control, trapping focus inside modals, and managing native keyboard behaviors.  
  * **Screen Reader Mechanics:** How the browser translates HTML trees into the Accessibility Tree (A11Y Tree) for assistive technologies.  
  * **The Browser Parsing Start:** Introduction to how the browser downloads HTML and begins constructing DOM nodes.  
* **Capstone Project Integration:** Setup the semantic shell of the *ScribeCollab* workspace editor, ensuring complete keyboard navigation compliance and screen-reader accessible input structures.

#### **Chapter 2: JavaScript Runtime: Execution Context, Scope, and Closures**

* **Prerequisites:** Chapter 1\.  
* **Difficulty:** Level B (JS / Browser)  
* **Core Curriculum Topics:**  
  * **Execution Context:** Creation vs. Execution phases, global context initialization, and function execution contexts.  
  * **The Call Stack:** Step-by-step trace of function invocation, call frames, stack pushing/popping, and maximum call stack errors (Stack Overflow).  
  * **Lexical Scope & Scope Chain:** Variable visibility environments, nested function blocks, and outer scope resolution.  
  * **Closures Under the Hood:** How functions retain references to their lexical environment even when executed outside their original scope.  
  * **Closures in Practice:** Constructing private variables, state encapsulation, and modular function patterns.  
* **Capstone Project Integration:** Build the core logic of the *ScribeCollab* state capture system using nested closures to securely preserve workspace user configurations without exposing global variables.

#### **Chapter 3: The JavaScript Memory Model & Object References**

* **Prerequisites:** Chapter 2\.  
* **Difficulty:** Level B (JS / Browser)  
* **Core Curriculum Topics:**  
  * **Stack vs. Heap Memory allocation:** Value types (primitives stored directly on the stack) vs. reference types (objects allocated in the heap).  
  * **Primitive vs. Reference Behaviors:** Assignment by value vs. assignment by reference, memory pointer copying, and variable mutations.  
  * **Garbage Collection Foundations:** Reachability algorithms, reference counting limits, and generational mark-and-sweep collections.  
  * **The Prototype System:** Constructor functions, prototype objects, the internal prototype chain (\[\[Prototype\]\] / \_\_proto\_\_), and Object.create().  
  * **Method delegation:** How the browser resolves property access on arrays, custom classes, and raw objects via Function.prototype.  
  * **Explicit context binding (this keyword):** Trace this binding behaviors through implicit call targets, explicit bindings (.call(), .apply(), .bind()), the new instantiation operator, and arrow function lexical binding.  
* **Capstone Project Integration:** Design the collaborative document structure using prototypical inheritance, ensuring deep nested document patches are cloned immutably rather than mutated by reference.

#### **Chapter 4: JavaScript Asynchronous Runtime & The Event Loop**

* **Prerequisites:** Chapter 3\.  
* **Difficulty:** Level C (JS / Browser)  
* **Core Curriculum Topics:**  
  * **Single-Thread Constraint:** Understanding why JavaScript is synchronous and single-threaded at its execution engine core.  
  * **Asynchronous Web APIs:** Offloading time delays and file access tasks to browser background threads (timers, network sockets).  
  * **Task Queue (Macrotask Queue):** The execution pipeline for setTimeout, setInterval, and I/O callbacks.  
  * **Microtask Queue (Promise Queue):** The high-priority pipeline for Promises (.then/.catch), async/await resumptions, and MutationObserver actions.  
  * **The Event Loop Execution Pass:** Step-by-step verification of how the Event Loop checks the Call Stack, completely flushes the Microtask Queue, renders updates, and processes a single Macrotask.  
* **Capstone Project Integration:** Implement the *ScribeCollab* live-saver queuing scheduler, ensuring background save operations execute as macrotasks to keep the high-priority UI interactive.

#### **Chapter 5: Browser Web APIs, DOM Orchestration, and Web I/O**

* **Prerequisites:** Chapter 4\.  
* **Difficulty:** Level C (JS / Browser)  
* **Core Curriculum Topics:**  
  * **DOM Selection & Mutators:** Native programmatic access via querySelector, custom traversal, and modifying text nodes safely.  
  * **DOM Observers:** Tracking DOM tree mutations via MutationObserver, element box dimensions via ResizeObserver, and viewport tracking via IntersectionObserver.  
  * **Web Storage Systems:** Synchronous storage limits in localStorage and sessionStorage.  
  * **Extended Web APIs:** Clipboard interaction, History navigation stacks, URL parameter serialization, and platform-level features (Notifications, Geolocation).  
  * **Stream-Oriented HTTP requests:** Fetch API execution depth. Typing Request, Response, and Headers. Utilizing AbortController to cancel active requests, and handling stream data chunks.  
* **Capstone Project Integration:** Bind the *ScribeCollab* document preview window to an IntersectionObserver to trigger lazy-loading of heavy markdown components, and manage offline backups inside localStorage using AbortController safeguards during save requests.

### **PHASE 2: TYPESCRIPT & MODERN BUILD TOOLING**

#### **Chapter 6: TypeScript Foundations & Modern Build Tooling**

* **Prerequisites:** Phase 1 Complete.  
* **Difficulty:** Level A (TS / Build)  
* **Core Curriculum Topics:**  
  * **What is TypeScript?:** The role of compile-time static analysis in preventing dynamic runtime crashes.  
  * **Package Management Ecosystem:** The mechanics of package.json, dependency matching engines, and differences between npm and pnpm.  
  * **Bundlers & Build Tools:** High-level evolution from Webpack conceptual configurations to modern tooling like Vite and Turbopack.  
  * **Tree Shaking & Code Splitting:** How static analysis allows modern compilers to prune unused code branches (Dead Code Elimination).  
  * **Type Annotations & Annotating Functions:** Explicit parameter bindings, return type annotations, type inferences, and function signatures.  
  * **Basic Type Systems:** Primitive types, Literal types, Type Assertions (as), Union types, and Intersection types.  
  * **Variable Escapes:** Why any destroys code safety, using unknown for safe verification, never for exhaustive matches, and void.  
  * **Collection Typings:** Strongly-typed arrays, readonly collection protections, tuples, and variadic tuples.  
* **Capstone Project Integration:** Initialize the compile pipeline for the *ScribeCollab* workspace workspace using a structured pnpm monorepo layout, configure strict compiler modes inside tsconfig.json, and define the strict types for Markdown document segments.

#### **Chapter 7: Advanced TypeScript & Runtime Validation**

* **Prerequisites:** Chapter 6\.  
* **Difficulty:** Level C (TS)  
* **Core Curriculum Topics:**  
  * **TypeScript Type Erasure:** Understanding that TS types exist purely at compile time and disappear completely in target JavaScript files.  
  * **Advanced Meta-Types:** Extracting property structures using keyof and values using typeof.  
  * **Complex Mapping Transforms:** Indexed Access Types, Mapped Types, and Template Literal Types.  
  * **Logical Types:** Conditional Types, using infer for automatic nested type extractions, and Distributive Conditional Types.  
  * **Type Enforcements:** Branded Types (nominal typing tags) to enforce structural validity, and Recursive Types for nested data models.  
  * **Advanced Utilities:** Pick, Omit, Partial, Required, Exclude, Extract, Record, ReturnType, InstanceType, and Awaited.  
  * **Runtime Validation Boundaries:** Why compile-time checks cannot protect against raw, unknown API inputs. Writing schemas using Zod to enforce data contracts at runtime.  
* **Capstone Project Integration:** Build the document update pipeline using deep recursive mapped types to track history state, and write robust Zod validation schemas to sanitize collaborative workspace payloads sent over external networks.

### **PHASE 3: REACT SYSTEM ARCHITECTURE (THE RENDERING ENGINE)**

#### **Chapter 8: React Philosophy & Component Composition**

* **Prerequisites:** Phase 1 and 2 Complete.  
* **Difficulty:** Level A (React)  
* **Core Curriculum Topics:**  
  * **React Architecture Theory:** Designing UI as a pure, deterministic function of state: ![][image1].  
  * **Virtual DOM Mechanics:** Building lightweight JS descriptions of the UI to calculate delta-changes before modifying real DOM nodes.  
  * **JSX Under the Compilation Lens:** Translating declarative tags into native JS function calls (jsx() / createElement()).  
  * **Component Assembly:** Function component nesting, child composition targets, and typing the children prop.  
  * **Dynamic UI Adjustments:** Controlled rendering loops using .map() and the critical importance of keeping stable, unique keys.  
  * **React Portals:** Breaking elements out of parent DOM trees using createPortal() for complex overlays (modals, dropdown lists).  
* **Capstone Project Integration:** Construct the workspace container layout using React Portals to host isolated modal components (like share menus and settings screens) without style leakage.

#### **Chapter 9: Core React Hooks & State Orchestration**

* **Prerequisites:** Chapter 8\.  
* **Difficulty:** Level B (React)  
* **Core Curriculum Topics:**  
  * **State Hook Foundations:** Managing local element updates using useState and state updates batching behavior.  
  * **State Immutability and State Lifting:** Ensuring structural sharing on update cycles, and lifting state parameters upwards to sync siblings.  
  * **Interactive Controls:** Controlled Forms vs. Uncontrolled Forms.  
  * **Effect Management (useEffect):** Executing side-effects, binding dependency arrays, and return cleanup handlers.  
  * **Persistent Variable Storage (useRef):** Accessing underlying elements, and keeping mutable variables across renders.  
  * **Context API Orchestration:** Creating Context Providers, using Consumers, and evaluating context updates performance.  
  * **Custom Hooks Construction:** Abstracting repeated state logic into pure reusable hooks using custom TypeScript signatures.  
* **Capstone Project Integration:** Implement a custom useDocumentSync hook that manages state synchronization with local browser storage, cleans up active timer callbacks, and registers keyboard listeners.

#### **Chapter 10: React Rendering Internals & Concurrent Mode**

* **Prerequisites:** Chapter 9 & Chapter 2\.  
* **Difficulty:** Level C (React)  
* **Core Curriculum Topics:**  
  * **Fiber Engine Architecture:** React's singly-linked list tree structure (child, sibling, return) acting as virtual stack frames.  
  * **The Render and Commit Cycle:** Complete isolation between the asynchronous Render Phase and the synchronous DOM Commit Phase.  
  * **Double-Buffering Tree Swaps:** How React builds a background Work-In-Progress Tree to match the active Current Tree.  
  * **The Scheduler Execution Priorities:** Task slicing, time-division, and utilizing useTransition and useDeferredValue to bypass input lag.  
  * **React Compiler (React Forget):** The future direction of automatic memoization, and why manual hooks like useMemo and useCallback are bypassed by modern compilers.  
  * **Performance Diagnostics:** Mastering Chrome Performance panel tracking, React Profiler measurements, Flamegraph analyses, and Component mounting audits.  
* **Capstone Project Integration:** Profile the *ScribeCollab* workspace during fast, continuous keystrokes. Use useTransition to split markdown rendering (low-priority) from the text editor cursor position (high-priority) to eliminate layout stutters.

#### **Chapter 11: Advanced Forms, Validation, & Store Architectures**

* **Prerequisites:** Chapter 10 & Chapter 7\.  
* **Difficulty:** Level B/C (React)  
* **Core Curriculum Topics:**  
  * **Form Performance Boundaries:** The high-frequency input cost of controlled elements compared to native uncontrolled elements.  
  * **React Hook Form (RHF) Architecture:** Subscribing to specific input state changes via reference pointer associations to minimize re-renders.  
  * **State Engine Scaling:** Defining the performance limits of the Context API under high-frequency updates.  
  * **Zustand Store Mechanics:** Creating external client stores, consuming state slices using strict selectors, and using modular store patterns.  
  * **Synchronizing External Stores:** The danger of UI tearing under concurrent rendering, and resolving state mismatches using React 18's useSyncExternalStore.  
* **Capstone Project Integration:** Migrate the *ScribeCollab* workspace core document state into an optimized Zustand store, configure structural slicing, and implement a type-safe form for document permissions utilizing React Hook Form and Zod schemas.

#### **Chapter 12: React Error Handling, Suspense, and List Virtualization**

* **Prerequisites:** Chapter 11\.  
* **Difficulty:** Level C (React)  
* **Core Curriculum Topics:**  
  * **React Error Boundaries:** Catching uncaught runtime rendering errors using class components, rendering fallback templates, and handling recoverable errors in React 18\.  
  * **Suspense Boundaries:** Coordinate async data loads, defining fallback templates, and configuring dynamic code loading with React.lazy().  
  * **DOM Virtualization Engine:** The rendering cost of massive lists. How to compute dynamic heights and scroll position updates via TanStack Virtual.  
* **Capstone Project Integration:** Add an Error Boundary to isolate markdown compilation errors from crashing the main editing workspace. Implement a virtualized navigation menu that loads 5,000+ workspace logs instantly without slowing down browser paint performance.

### **PHASE 4: NEXT.JS & ENTERPRISE ARCHITECTURE**

#### **Chapter 13: Next.js Layout Architecture, Navigation, & Accessibility (A11Y)**

* **Prerequisites:** Phase 3 Complete.  
* **Difficulty:** Level A (Next.js)  
* **Core Curriculum Topics:**  
  * **Why Meta-Frameworks?:** Differentiating SSR, CSR, and Static Site Generation (SSG).  
  * **The Next.js App Router Structure:** Layouts, Templates, nested page hierarchies, and Route Groups.  
  * **Navigating Dynamic Routes:** Dynamic segments (\[id\]), client navigation via the \<Link\> component, and prefetching.  
  * **Internationalization (i18n):** Configuring localized paths, dynamic translation routes, and localized document rendering.  
  * **Accessible Navigation (A11Y):** Focus shifting during route transitions and managing screen reader notification cues.  
* **Capstone Project Integration:** Reconstruct the *ScribeCollab* dashboard layout within Next.js App Router, complete with multi-language routes and accessible keyboard navigation models.

#### **Chapter 14: Next.js Rendering Strategies & Server Architecture**

* **Prerequisites:** Chapter 13\.  
* **Difficulty:** Level C (Next.js)  
* **Core Curriculum Topics:**  
  * **Modern Rendering Strategies:** SSG, Static SSR, Dynamic SSR, Incremental Static Regeneration (ISR), and Partial Prerendering (PPR).  
  * **React Server Components (RSC):** Rendering on the server, keeping JS bundles lightweight, and accessing secure servers.  
  * **Client Components Boundary:** Understanding the 'use client' directive and hydration mismatch errors.  
  * **The Serialization Bridge:** How Next.js serializes data to pass it over the Server/Client boundary.  
  * **Advanced Caching & Revalidation:** Next.js fetch cache caching pipelines, tag-based cache revalidations, and static vs. dynamic rendering.  
  * **Asynchronous Server Actions:** Safe mutations from client pages directly into backend logic.  
* **Capstone Project Integration:** Convert the document metadata panel into a pure Server Component, configure live document fetches using streamed Server Actions, and handle database updates with validation checks.

#### **Chapter 15: APIs, Middleware, & Modern Security Shields**

* **Prerequisites:** Chapter 14\.  
* **Difficulty:** Level C/D (Next.js)  
* **Core Curriculum Topics:**  
  * **Dynamic Route Handlers:** Creating custom API routes (GET, POST, PATCH, DELETE) and streaming HTTP responses.  
  * **Edge Middleware:** Intercepting HTTP requests, rewriting paths, managing redirects, and writing lightweight auth middleware.  
  * **Search Engine Optimization (SEO) & Metadata:** Dynamic Metadata API declarations, OpenGraph headers, Twitter cards, robots, and sitemap XML files.  
  * **Environment Variables & Production Secrets:** Restricting server-only secrets vs. exposing public variables (NEXT\_PUBLIC\_).  
  * **Advanced Web Security Shields:** Deploying defense layers against XSS, CSRF, DOM Clobbering, and configuring Content Security Policy (CSP) headers.  
* **Capstone Project Integration:** Write a Next.js Edge Middleware to intercept unauthorized users, configure dynamic OG meta cards for markdown sharing, and implement a strict CSP header template to shield *ScribeCollab* from malicious script injections.

#### **Chapter 16: Enterprise Auth, Deployment, & Performance Auditing**

* **Prerequisites:** Phase 4 Core.  
* **Difficulty:** Level D (Next.js)  
* **Core Curriculum Topics:**  
  * **Session Management & Auth:** Integrating Auth.js, JWT operations, OAuth, and Role-Based Access Controls (RBAC).  
  * **Enterprise Build Pipeline:** Turbopack optimization, Monorepo management, and utilizing modern JS bundlers.  
  * **Docker Containerization & Deployment runtimes:** Containerizing Next.js for production, comparing Vercel Serverless with self-hosted Node.js runtimes, and configuring Edge platforms.  
  * **Telemetry & Production Monitoring:** Real-world metrics monitoring (LCP, CLS, INP) using PerformanceObserver and gathering performance reports via browser sendBeacon APIs.  
* **Capstone Project Integration:** Containerize *ScribeCollab* inside a secure multi-stage Docker environment, setup dynamic authentication checks using JWT tokens in Middleware, and write an automatic performance reporter that pipes Core Web Vitals to a remote analytics route.

## **🛠️ DOWNSTREAM GENERATOR DIRECTIVES (FOR EACH LESSON)**

To ensure consistency across all generated lessons, the downstream generator **MUST** adhere to the following 14 structured sections:

1. **LEARNING OBJECTIVES:** Explicitly outline the measurable skills using Bloom’s Taxonomy verbs.  
2. **MOTIVATION:** Detail the architectural problems, history, and real-world costs of ignored patterns.  
3. **CORE THEORY:** Deeply explain execution paths, variables, and systems diagrams.  
4. **VISUAL DIAGRAMS:** Construct exhaustive Mermaid diagrams illustrating execution flows.  
5. **STEP-BY-STEP WALKTHROUGHS:** Map interaction lifecycles with exact timelines.  
6. **INTERNAL IMPLEMENTATION:** Explain how React, Next.js, or browser engines implement these features under the hood.  
7. **CODE EXAMPLES:** Provide:  
   * A *minimal* example.  
   * A *practical* real-world example.  
   * A *production-ready* pattern.  
   * An *incorrect* anti-pattern example, followed immediately by its *corrected* implementation.  
8. **COMMON MISTAKES:** Highlight Developer traps at Junior, Mid-Level, and Production/Senior stages.  
9. **PERFORMANCE ANALYSIS:** Analyze execution via Time Complexity (![][image2]), memory overhead, and frame drops.  
10. **SECURITY INVENTORY:** Outline vulnerabilities, secure validation checks, and browser sandboxing rules.  
11. **TECHNOLOGY COMPARISONS:** Provide highly objective markdown tables comparing alternate tool paths.  
12. **ENGINEERING DECISIONS:** Answer the business, maintenance, and trade-off considerations.  
13. **EXERCISES:** Provide Easy (comprehension), Medium (implementation), and Hard (architectural evaluation) assessments.

## **🧭 CAPSTONE ASSESSMENT MATRIX & GLOSSARY**

### **1\. CAPSTONE GRADING & RUBRIC SCALING**

To evaluate the student's *ScribeCollab* implementation throughout the course, the downstream content generator must evaluate based on these performance tiers:

| Dimension | Poor (Junior / Intern baseline) | Meets Criteria (Mid-level Standard) | Exceptional (Lead Architect Standard) |
| :---- | :---- | :---- | :---- |
| **A11Y Integration** | Accessible nodes are ignored; keyboard traps are present; no ARIA annotations. | Semantic HTML is correct; focus management works for basic modals; screen readers can read layouts. | Complete A11Y Tree compliance; custom focus traps; screen-reader notifications read live sync states. |
| **Type Safety** | Pervasive use of any types; type assertions (as) bypass safety checks; schemas are absent. | Clean type structures; interfaces use proper generics; type-checking passes. | Nominal branded types protect the boundary paths; deep recursive conditional types; zero assertions. |
| **Render Tuning** | Typing in the document lags; full-page re-renders occur on every keyboard click. | Components use proper keys; standard caching keeps page loads quick. | Concurrent time-slicing keeps typing under 5ms; Zustand selector caching blocks unnecessary re-renders. |
| **Security Shielding** | Script text renders unescaped; state mutations let users modify nested values. | HTML inputs are sanitized; CORS config matches standard APIs. | Strict CSP headers block execution of untrusted scripts; nominal branded types enforce strict data paths. |

### **2\. CORE SYSTEM GLOSSARY**

The downstream generator must define and reference these terms across the chapters:

* **Mechanical Sympathy:** Programming with an understanding of how the underlying hardware, browser engine, or framework compiler actually runs, avoiding blind reliance on high-level abstractions.  
* **Execution Context:** The wrapper environment created by the JS engine to parse and execute code. It contains the local scope variable environment, prototype chain links, and the explicit this binding value.  
* **Fiber:** React’s internal data object representing a unit of component state work. Fibers serve as virtual stack frames to allow non-recursive, async interruptible UI calculations.  
* **Hydration Mismatch:** A state mismatch where the HTML delivered by the server differs from the initial virtual DOM tree generated in the browser, forcing React to discard server-rendered nodes.  
* **Tearing:** A visual artifact in concurrent UI rendering where different parts of the DOM display different values for the same global state during a single paint cycle.  
* **Branded Type:** A compile-time technique that appends a unique compile-time symbol to a primitive type (like string or number), forcing developers to sanitize values before passing them into secure targets.

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAaCAYAAAC+aNwHAAAB50lEQVR4XpVTy0rDQBTNUBeKUQQbo6aZSdLQfoDgL+hCxJ2iH+IHiCC4EangD7hz505cFP0F3RRXIhXcFATdaT0zybzSpNUDk9ycc+6deyeJ4wCEXwSIiMWzJqVU4NRDlqSJYmYZM8IVLZOe/4EoihYYYysoUlNkVT05Jl9IumCUfeDep5S+MEa/EZ+naTpfPSzQaDRmYDyNo+gkCIJFaUInG5SxAYr14EmtJAmYlrHuUWBQVh3aLmX0B/dbsb82EQfVb9DyEDucCUKJVqkpFL/GGtoKETMPMWc/DLP29JxZRLINCXxX3IsupmW6E8exz0l00TFyZWp+JY7n1V1s0uXe2CwQhuE2SD7bpiJzmAMgOYHvTY4g4Pv+LIg7iA/tVntOCdbo4oHgjDpiVMpeleTVPZdmbXU9z3P5rDpHg786ePrZWbEjbSH8YCg/GFHAyjLA306e/NhsJkvWDhAPITwFq0G9+GtJQOdf4gAHvq7Z3MVv2adKezAwbXBqSNrH+kySpKVp47eXQBdbML6jyBfiS8THWM+Co/Qgz8tR7E+jhuQ1vM49rB2syBnjtoVKmwFj5BJiRB1TdJJQqdvIvxnjx/srRhNIGWnAGrIC6hvmcWlYgNk5j2QBEStFUeWwlGqbgrDYvl/9FFYtOpWwqQAAAABJRU5ErkJggg==>