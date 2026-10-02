# MerRec repository instructions

These instructions apply to the entire repository. Read this file before editing.

## Working style

- Work from the repository root: `D:\MerRec`.
- Use PowerShell-compatible commands on Windows.
- Inspect the relevant implementation and its callers before changing code. Prefer `rg` and `rg --files` for discovery.
- The worktree may contain user changes. Preserve unrelated modifications and never reset, revert, delete, or reformat them.
- Complete requested changes, run checks proportional to the change, and report what changed and what remains mocked or disconnected.
- Keep user-facing text in Vietnamese unless the surrounding screen already uses another language.
- Do not invent successful backend behavior. Several backend and test files are still TODO placeholders.

## Project map and sources of truth

- `frontend/`: Next.js App Router application using React and TypeScript.
- `frontend/src/app/`: routes, layouts, route handlers, and page-specific CSS.
- `frontend/src/components/`: reusable UI components.
- `frontend/src/lib/merrecData.ts`: frontend product types and the small preview catalog.
- `frontend/src/lib/catalog-server.ts`: server-only bridge from Next.js to Python catalog operations.
- `scripts/storefront_catalog.py`: reads the serving catalog and resolves product details/images for the website.
- `scripts/storefront_images.py`: validates image URLs, keeps a durable local outbox, and synchronizes images to PostgreSQL.
- `data/processed/recommender/serving/item_catalog_full.parquet`: current full product catalog. It is the source of truth for product metadata when present.
- `database/schema.sql`: intended PostgreSQL schema. Check its actual contents before relying on a table or column.
- `training/`: preprocessing, training, evaluation, notebooks, and model artifacts.
- `tests/`: Python tests. Files containing only TODO text are placeholders, not meaningful coverage.

Do not add back the removed legacy CSV resolver scripts (`split_csv.py`, `resolve_images_to_sql.py`, or `import_products.py`) unless the user explicitly asks to restore that workflow.

## Frontend conventions

- Use App Router conventions and keep server-only Node/Python bridge code out of client components.
- Add `"use client"` only when a component needs state, effects, event handlers, browser APIs, or client navigation.
- Reuse the global font and existing design tokens from `frontend/src/app/globals.css`.
- Prefer existing shared components and `lucide-react` icons over emoji or new dependencies.
- Keep controls keyboard accessible and provide labels for icon-only buttons.
- Make new layouts responsive at desktop and mobile widths.
- When logic is intentionally mocked, label it clearly in the UI or response. Do not imply that profile, authentication, order, or settings data was persisted when no backend call exists.
- Public assets must physically exist under `frontend/public`; reference them from the browser as `/filename.ext`. Verify the file before adding or changing an asset path.
- Do not use remote product images as authoritative product metadata. Product name, category, brand, condition, size, color, and description must come from the catalog/database.
- If a product has no description, display a neutral missing-state message. Do not synthesize a description from potentially incorrect categories.

## Product and image flow

The active storefront flow is:

1. Next.js calls `frontend/src/lib/catalog-server.ts`.
2. The bridge executes `scripts/storefront_catalog.py`.
3. Product metadata is read from `item_catalog_full.parquet`.
4. For images, `scripts/storefront_images.py` first reuses verified local results or searches and validates candidates.
5. Verified image URLs are stored in `data/storefront/product_images.sqlite3`; pending records are retained in `image_outbox` until synchronization to PostgreSQL succeeds.
6. PostgreSQL uses `DATABASE_URL` from `.env` and the `products` / `product_images` tables.

Preserve these guarantees when editing the image flow:

- Reuse a stored image before performing a new search.
- Only persist verified, publicly reachable HTTPS image URLs.
- A PostgreSQL outage must not lose a verified result or prevent the product page from loading.
- Avoid duplicate `(item_id, image_url)` records.
- Never print, commit, or expose `DATABASE_URL` or other `.env` values.
- Do not commit SQLite databases, raw data, processed datasets, model artifacts, logs, or secrets.

## Mandatory end-to-end production workflow

For work described as complete, production-ready, or end to end, verify the entire request path. A page that only looks correct is not a complete feature.

### Define and trace the behavior

- Turn the request into acceptance criteria covering success, loading, empty data, invalid input, dependency failure, retry, and persistence after refresh or process restart.
- Identify demo-only behavior before editing. Implement missing layers that are in scope, or report them explicitly; never disguise mock behavior as a successful production write.
- Inspect every caller and consumer of a shared type, route, schema, component, or script before changing it.
- Trace the applicable path from user action -> React -> Next.js route/server function -> Python service -> PostgreSQL/catalog/model -> response -> rendered state -> fresh read.
- Define request and response shapes in code. Keep IDs, money units, timestamps, nullability, and enums consistent across layers.
- Never silently fall back to demo data after a production dependency fails. Failed writes must use meaningful HTTP status codes and stable, safe error bodies.

### Persistence and server guarantees

- Validate and normalize input at the server boundary; browser validation is only for user experience.
- Use parameterized SQL and transactions. Never concatenate user input into SQL or shell commands.
- Make retryable writes idempotent and prevent duplicates with database constraints where possible.
- Make schema changes reviewable through explicit SQL or migrations. Do not silently mutate a shared production schema at startup.
- Define behavior for missing, inactive, and deleted records while preserving referential integrity.
- Add timeouts and bounded retries to network, database, subprocess, and image operations.
- Keep PostgreSQL as the durable production source. Any cache or outbox needs an explicit synchronization and recovery path.

### Complete UI behavior

- Every asynchronous screen must handle loading, success, empty, validation error, server error, and retry states.
- Prevent duplicate submissions and show pending, success, and failure states.
- After a successful mutation, refresh or invalidate displayed data and verify the value survives a fresh page load.
- Keep forms accessible with associated labels, keyboard operation, focus management, and specific inline errors.
- Verify normal desktop and narrow mobile layouts.

### Security and privacy

- Enforce authentication, authorization, and resource ownership on the server. Hiding a control is not authorization.
- Do not expose secrets, password hashes, internal errors, absolute paths, SQL, or stack traces to the browser.
- Preserve SSRF protections for external image URLs and validate redirects.
- Never log passwords, tokens, cookies, addresses, phone numbers, or sensitive request bodies.
- Use secure cookie and session settings when authentication is implemented.

### Verification gates

Run checks in increasing scope and fix failures caused by the change:

1. Static checks: `git diff --check`, TypeScript typecheck, lint, and relevant Python syntax/import checks.
2. Unit tests for validation, transformations, business rules, and error mapping.
3. Integration tests through the route/service using an isolated fixture or disposable test database.
4. End-to-end smoke test from the user-facing entry point through persistence and back to the rendered result.
5. `npm run build` for changes involving routes, rendering boundaries, configuration, or deployment.

For persisted mutations, verify at minimum:

```text
create/change through UI or public API
  -> observe success
  -> perform a fresh read or reload
  -> observe the stored value
  -> submit invalid input and observe safe failure
  -> make a dependency unavailable and observe a recoverable error
```

If a service cannot run locally, replace only that boundary with an isolated test double and state exactly what was not exercised.

### Operations and handoff

- Read required configuration from environment variables and keep `.env.example` synchronized without secrets.
- Add concise server logs around failures and important transitions, using useful identifiers without sensitive values.
- Consider concurrent requests, process restarts, stale caches, database outages, and repeated requests.
- Do not deploy, migrate a shared database, commit, or push unless the user explicitly requests it.
- For deployment work, prepare a rollback path and verify health after release.
- Never claim zero defects. Do not say “production-ready” or “end to end complete” without listing the exercised layers, exact checks and results, schema impact, remaining mocks, external dependencies, untested cases, and recovery considerations.
- A green typecheck alone is not end-to-end evidence. If a required gate was skipped, say which one and why.

## Commands

Use the existing virtual environment when available:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_storefront_images -v
.\.venv\Scripts\python.exe -m unittest tests.test_local_eda -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Frontend checks run from `frontend`:

```powershell
npm run typecheck
npm run lint
npm run build
```

Use the smallest relevant check first:

- UI/CSS or TypeScript edit: `npm run typecheck`, then lint the changed file or run `npm run lint` for broader changes.
- Route/build configuration edit: typecheck and `npm run build`.
- Storefront image edit: `tests.test_storefront_images`.
- EDA/notebook pipeline edit: `tests.test_local_eda`.
- Cross-cutting Python edit: relevant targeted tests, then unittest discovery if justified.

Do not create tests that only mirror implementation details. Add tests for behavior that can regress, especially persistence, validation, routing, and error handling.

## Data and generated files

- Large data and artifacts are intentionally ignored by Git. Do not force-add them.
- Do not rewrite notebooks, generated catalogs, lockfiles, or SQL dumps unless the task requires it.
- Treat `frontend/src/lib/catalog-preview.json` as generated preview data; do not hand-edit individual products unless explicitly requested.
- Before deleting a script or asset, search all code, documentation, tests, notebooks, and Git history for references, then state exactly what was removed.

## Completion checklist

Before finishing a change:

1. Review `git diff --check` and the relevant diff without touching unrelated changes.
2. Run the smallest meaningful validation commands.
3. Confirm new routes and asset paths exist.
4. State any untested runtime dependency, missing data, mock-only behavior, or external service requirement.
5. Do not commit or push unless the user explicitly requests it.
6. For end-to-end work, verify a real round trip through every changed layer and persistence after a fresh read.
7. State evidence and remaining risk instead of claiming the result has no possible defects.
