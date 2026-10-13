# Frontend design refresh

## Audit

The existing frontend uses React 18, TypeScript, Vite, React Router, Lucide
icons, and a single CSS design system; no animation library is installed.
Admin and public layouts are separate, public data comes from the existing
published-only API (or clearly marked fixtures in demo mode), and admin
mutations remain routed through the authenticated API client. The stylesheet
already had some entrance, hover, and reduced-motion rules, but later palette
overrides made the public site light and visual treatments inconsistent.

## Implementation plan and delivered scope

1. Preserve the current route tree, API calls, CSRF/auth handling, fixture
   boundaries, and publishing safeguards. No backend or service calls are
   introduced by this design change.
2. Consolidate the effective look using an end-of-file design layer: midnight
   navy surfaces, violet/indigo light fields, restrained cyan and amber status
   accents, layered public/editorial artwork, and richer admin workflow
   surfaces.
3. Apply shared motion tokens and CSS transitions to page entry, story cards,
   controls, navigation, forms, status surfaces, and workflow panels. Use a
   small IntersectionObserver hook for viewport reveals; do not add a package.
4. Keep public reading high contrast and distinct from the admin studio. Add
   narrow-screen overrides for navigation, cards, forms, and workspace grids.
5. Respect `prefers-reduced-motion`, retain visible keyboard focus, and avoid
   inventing audio waveforms, live status, or statistics.
6. Run frontend tests and the production build, then inspect public/admin
   routes and responsive/reduced-motion states in the local browser when
   available.

## Files in scope

- `frontend/src/styles.css`: premium visual tokens, public/admin surface
  styling, responsive rules, and reduced-motion-aware animation system.
- `frontend/src/App.tsx`: route-aware viewport reveal behavior, with no
  changes to data or backend contracts.
- `docs/FRONTEND_DESIGN_REFRESH.md`: audit and implementation record.

## Out of scope

No new dependency, real audio/TTS behavior, backend or API changes, live
Google/Gemini/GitHub calls, publishing changes, deployments, or credential
changes. Any integration not already implemented remains labeled as such.
