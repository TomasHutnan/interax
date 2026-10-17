<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

When writing code, make sure to always put props into brackets, even when it is a string. Put hooks and contexts into their respective directories in `lib/`, for other purposes, like utilities, you may create other files and directories inside `lib/`. Put components inside `/components` and create relevant directories as needed. For UI components, use what is provided inside components/ui, they are shadcn/ui components - you do not need to install any others (as I=the user will do it for you before asking you to do something with them), unless you explicitly need them.

<!-- END:nextjs-agent-rules -->
