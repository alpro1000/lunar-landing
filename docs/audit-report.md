# ONEIROSCOP+LUNAR — Audit of `lunar-landing`

## Repository snapshot
- **Type**: static client-side app with vanilla HTML/CSS/JS delivered from `index.html`.
- **Primary assets**: lunar calendar logic (`scripts/calendar.js`), dreambook search and heuristic analysis (`scripts/dreambook.js`), curated symbol dataset (`data/dreams_curated.json`).
- **Automation**: GitHub Actions for ETL refresh, repository inventory, and structure scaffolding (`.github/workflows/*.yml`).

## Structure & separation of concerns
- Single-page front-end (`index.html`) bundles calendar UI, dream interpretation form, and localized content. No component modularization or build tooling.
- Styles split between base theme (`styles/theme.css`), typography (`styles/typography.css`), and responsive overrides (`styles/responsive.css`), but CSS variables lack a design token source of truth.
- Back-end or API layer is absent; functionality is limited to browser-based lookups against static JSON.
- `etl/` directory mixes configuration (`sources_config.yml`), raw inputs (`etl/input`), mapping tables (`symbols_map.json`), and executable (`etl_dreams.py`) without packaging or tests.

## Data acquisition & processing
- `etl/etl_dreams.py` implements multi-source scraping/downloading (Zenodo, Dryad, Figshare/Donders, Monash, user uploads) with minimal validation and no retry/backoff strategy. Licensing considerations are documented only implicitly in comments.
- Dependencies pinned loosely in `etl/requirements.txt`; no lockfile or reproducible environment definition.
- Output `data/dreams_curated.json` is a large JSON array stored in repo; no pagination, indexing, or metadata versioning.
- Lack of HVdC schema or codebook; symbols map currently focused on folk interpretations.

## Front-end functionality & UX
- Calendar logic in `scripts/calendar.js` couples internationalization dictionaries, lunar day tables, and DOM manipulation in one file (>1k lines) without modular structure, making future enhancements (accordion month view, dynamic data) hard to manage.
- Dream analysis flow in `scripts/dreambook.js` matches keywords against static dataset with fuzzy scoring, but lacks confidence calibration and does not expose HVdC dimensions.
- Accessibility gaps: minimal ARIA usage, no keyboard shortcuts for calendar toggles, dark theme contrast not evaluated.
- No support for authentication, user storage, or chat paradigm; current UX is static form interactions.

## DevOps & quality
- No unit or integration tests. GitHub Actions only cover ETL execution and repo inventory; no CI for linting, formatting, or deployment packaging.
- Missing containerization/infra-as-code. Deployment instructions limited to GitHub Pages static hosting.
- Monitoring, logging, or error reporting absent.

## Key risks & blockers for ONEIROSCOP+LUNAR
1. **Monolithic front-end**: Large imperative scripts impede reuse for chat UI or advanced calendar components.
2. **Data governance**: Reliance on scraped datasets without explicit license tracking; absence of schema validations complicates HVdC integration.
3. **No back-end**: Required API endpoints (`/sleep/analyze`, `/lunar`, `/recommend`, etc.) do not exist; architectural shift to full-stack needed.
4. **Testing debt**: Lack of automated validation for lunar calculations and dream symbol matching increases risk when integrating HVdC and LLMs.
5. **Scalability**: Static JSON dataset cannot scale to tens of thousands of dreams or support personalization, requiring database-backed services.

## Immediate remediation suggestions
- Establish mono-repo layout with `frontend/`, `backend/`, `etl/`, and `infrastructure/` packages to decouple concerns.
- Introduce package management (e.g., `pnpm` for front-end, `poetry`/`pip-tools` for Python ETL) and lock dependencies.
- Define data contracts for HVdC entities (codebook, annotations) and implement schema validation (Pydantic/Marshmallow) in the ETL pipeline.
- Bootstrap automated tests: lunar phase calculation unit tests, ETL smoke tests, JSON schema checks via CI.
- Plan migration path from static HTML to component-based framework (Next.js / React) with design system tokens to support required UX features.
