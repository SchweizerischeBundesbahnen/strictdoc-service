# CLAUDE.md

## Gotchas

- **PDF export is non-functional.** `/export?format=html2pdf` exists but fails because Chromium/ChromeDriver is intentionally not installed (image size). Do not suggest "fixing" the PDF endpoint without explicit approval.
- **Do not migrate the base image to Alpine.** tree-sitter fails to compile on Alpine arm64 — see `docs/alpine-not-supported.md` for the full reason before proposing any change here.
