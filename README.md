# Socialized — Ambient Worlds Content Engine

Socialized is a production web dashboard for creating and publishing long-form ambient video content. The current architecture uses **Vercel for the web app/API, Supabase for storage and job queues, and GitHub Actions as the production rendering and publishing worker**.

## Product

**Production URL:** https://socialized-self.vercel.app/

Use the production URL above for the live Socialized dashboard.

## Current production architecture

```text
User
  │
  ▼
Vercel — Socialized dashboard + API
  │
  ├── Image upload
  ├── Render job creation
  ├── YouTube OAuth
  ├── YouTube connection status
  └── Rendered-video library
  │
  ▼
Supabase — database + storage
  │
  ▼
GitHub Actions — render + publish worker
```

This documentation update is intentionally non-functional. It exists as a controlled deployment test: if Vercel cannot publish this commit after a successful build, the problem is outside the application code changed in the recent renderer commits.

## Ambient rendering

The production worker supports scene-aware ambience and procedural weather motion. Rain and snow are generated as seamless cyclic overlays and composited over the source environment image. Rendered videos can be reused from the library instead of rendered again.
