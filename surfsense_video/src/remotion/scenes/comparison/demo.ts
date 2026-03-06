/** Sample comparison data for Remotion Studio preview. */
import type { ComparisonSceneInput } from "./types";

export const DEMO_COMPARE_BINARY: ComparisonSceneInput = {
  type: "comparison",
  title: "Traditional vs AI-Powered",
  subtitle: "Software development approaches",
  groups: [
    {
      label: "Traditional",
      color: "#3b82f6",
      items: [
        { label: "Manual code reviews", desc: "Time-consuming peer reviews" },
        { label: "Waterfall planning", desc: "Sequential development phases" },
        { label: "Manual testing", desc: "QA team runs test suites" },
        { label: "Static documentation", desc: "Wikis and confluence pages" },
      ],
    },
    {
      label: "AI-Powered",
      color: "#10b981",
      items: [
        { label: "Automated analysis", desc: "AI-driven code review" },
        { label: "Agile with AI insights", desc: "Predictive sprint planning" },
        { label: "AI test generation", desc: "Auto-generated test cases" },
        { label: "Living documentation", desc: "AI-maintained docs" },
      ],
    },
  ],
};

export const DEMO_COMPARE_TABLE: ComparisonSceneInput = {
  type: "comparison",
  title: "Cloud Provider Comparison",
  subtitle: "Feature matrix across major platforms",
  groups: [
    {
      label: "AWS",
      color: "#FF9900",
      items: [
        { label: "Compute", desc: "EC2, Lambda, ECS" },
        { label: "Storage", desc: "S3, EBS, Glacier" },
        { label: "Database", desc: "RDS, DynamoDB, Aurora" },
        { label: "AI/ML", desc: "SageMaker, Bedrock" },
      ],
    },
    {
      label: "Azure",
      color: "#0078D4",
      items: [
        { label: "Compute", desc: "VMs, Functions, AKS" },
        { label: "Storage", desc: "Blob, Disk, Archive" },
        { label: "Database", desc: "SQL DB, Cosmos DB" },
        { label: "AI/ML", desc: "Azure AI, OpenAI" },
      ],
    },
    {
      label: "GCP",
      color: "#4285F4",
      items: [
        { label: "Compute", desc: "GCE, Cloud Run, GKE" },
        { label: "Storage", desc: "Cloud Storage, PD" },
        { label: "Database", desc: "Cloud SQL, Spanner" },
        { label: "AI/ML", desc: "Vertex AI, Gemini" },
      ],
    },
  ],
};

export const DEMO_COMPARE_LARGE: ComparisonSceneInput = {
  type: "comparison",
  title: "Framework Comparison",
  subtitle: "React vs Vue vs Svelte vs Angular",
  groups: [
    {
      label: "React",
      color: "#61DAFB",
      items: [
        { label: "Virtual DOM Diffing", desc: "Uses a lightweight in-memory representation of the UI to compute the minimal set of DOM mutations needed on each render cycle" },
        { label: "JSX Syntax", desc: "Combines JavaScript logic with HTML-like markup in a single file, enabling expressive component authoring with full language support" },
        { label: "Hooks API", desc: "Provides primitives like useState and useEffect for managing state and side effects in function components without classes" },
        { label: "Massive Ecosystem", desc: "Thousands of community-maintained libraries covering routing, state management, animation, forms, and more" },
        { label: "React Native", desc: "Enables building native iOS and Android applications using the same React component model and JavaScript codebase" },
        { label: "Server Components", desc: "Allows components to render on the server and stream HTML to the client, reducing bundle size and improving time-to-interactive" },
      ],
    },
    {
      label: "Vue",
      color: "#4FC08D",
      items: [
        { label: "Proxy-Based Reactivity", desc: "Leverages ES6 Proxy objects to track dependencies at a granular level, automatically re-rendering only the affected parts of the UI" },
        { label: "Single-File Components", desc: "Encapsulates template, script, and styles in a single .vue file with scoped CSS support for clean component boundaries" },
        { label: "Composition API", desc: "Organizes component logic into composable functions that can be shared and reused across components without mixins" },
        { label: "Official Ecosystem", desc: "Provides first-party solutions for routing with Vue Router and state management with Pinia, ensuring tight integration" },
        { label: "Nuxt.js Framework", desc: "A full-stack meta-framework offering SSR, static generation, API routes, and file-based routing out of the box" },
        { label: "Vapor Mode", desc: "An experimental compilation strategy that bypasses the virtual DOM entirely, generating direct DOM operations for maximum performance" },
      ],
    },
    {
      label: "Svelte",
      color: "#FF3E00",
      items: [
        { label: "Compile-Time Approach", desc: "Shifts reactivity and component logic to the build step, producing highly optimized vanilla JavaScript with zero framework runtime overhead" },
        { label: "Runes Reactivity", desc: "Introduces fine-grained reactive primitives that are compiled away, giving developers explicit control over state tracking and updates" },
        { label: "Minimal Boilerplate", desc: "Requires significantly less code than other frameworks for the same functionality, reducing cognitive load and maintenance burden" },
        { label: "Growing Community", desc: "A rapidly expanding ecosystem of libraries, tools, and learning resources backed by an enthusiastic open-source community" },
        { label: "SvelteKit Framework", desc: "Provides server-side rendering, API endpoints, file-based routing, and adapter-based deployment targets in a unified full-stack framework" },
        { label: "Tiny Bundle Sizes", desc: "Compiles components to surgically precise DOM updates, resulting in production bundles that are a fraction of the size of competing frameworks" },
      ],
    },
    {
      label: "Angular",
      color: "#DD0031",
      items: [
        { label: "Batteries-Included Framework", desc: "Ships with built-in solutions for routing, forms, HTTP, animations, and testing, so teams can start building without choosing third-party libraries" },
        { label: "TypeScript Native", desc: "Built from the ground up with TypeScript, offering first-class type safety, decorators, and IDE support throughout the entire framework" },
        { label: "Signals Reactivity", desc: "A modern fine-grained reactivity model that enables efficient change detection without Zone.js, improving performance and debuggability" },
        { label: "Enterprise Tooling", desc: "Mature CLI, schematics, and workspace management tools designed for large-scale teams and monorepo architectures" },
        { label: "Analog.js Meta-Framework", desc: "A community-driven meta-framework bringing file-based routing, API routes, and Vite-powered builds to the Angular ecosystem" },
        { label: "Dependency Injection", desc: "A hierarchical DI system that enables modular, testable, and scalable application architectures with provider scoping and lazy loading" },
      ],
    },
  ],
};
