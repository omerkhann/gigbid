# nestleaf-migration

## Overview
`nestleaf-migration` is a proof‑of‑concept repository that demonstrates the systematic migration of a large Vue.js codebase to React while preserving zero‑downtime operation. The project focuses on a property listings platform with ~140 UI components, routing, state management, and API integration. It showcases a component‑by‑component rewrite strategy, automated test conversion, and a dual‑runtime deployment model.

## Architecture
- **Component Layer**: Each Vue single‑file component (`*.vue`) has a corresponding React functional component (`*.tsx`). The React versions are placed under `src/react/` and mirror the original directory hierarchy.
- **Feature Flags**: A runtime flag (`USE_REACT`) toggles which implementation is rendered. The flag is read from an environment variable and injected via Webpack's DefinePlugin.
- **State Management**: Vuex stores are rewritten to Redux Toolkit slices. A thin adapter layer (`src/state/adapter.js`) synchronizes legacy Vuex state with the new Redux store during the transition period.
- **Routing**: Vue Router routes are duplicated in React Router v6. A wrapper component (`HybridRouter`) decides which router to mount based on the flag.
- **Build System**: Webpack 5 is configured with two entry points (`main-vue.js` and `main-react.js`). Both bundles are output to `dist/` and served by the same Express server.
- **Testing**: Jest + Vue Test Utils tests are migrated to React Testing Library. A migration script (`scripts/migrate-tests.js`) automates the conversion of test files.

## Getting Started
1. **Prerequisites**: Node.js >=18, npm >=9.
2. **Install dependencies**:
   ```bash
   npm ci
   ```
3. **Run in Vue‑only mode** (baseline):
   ```bash
   npm run dev -- --env USE_REACT=false
   ```
4. **Run in React‑only mode** (post‑migration):
   ```bash
   npm run dev -- --env USE_REACT=true
   ```
   The server will hot‑reload both Vue and React bundles.
5. **Build for production**:
   ```bash
   npm run build
   ```
   The output contains `bundle-vue.js` and `bundle-react.js`; the Express server selects the appropriate bundle based on the `USE_REACT` flag.

## Migration Workflow
- Identify a Vue component.
- Generate a React counterpart using `npm run generate:react <ComponentName>`.
- Implement the UI using JSX and migrate props/state.
- Add the component to the feature flag map in `src/featureFlags.js`.
- Run the test suite; ensure both Vue and React tests pass.
- Deploy the updated bundle behind a canary release.

The repository includes detailed scripts (`scripts/`) to automate component scaffolding, test conversion, and bundle verification, enabling a repeatable, low‑risk migration pipeline.
