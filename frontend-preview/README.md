# Continuum frontend preview

The original application was a standalone HTML prototype. It now includes a React 19 / TypeScript / Tailwind 4 component build and shadcn-compatible project structure. The existing workspace and local chat simulator remain in `index.html`; the React composer is mounted into it by the build.

## Paths

- `components/ui/ai-chat-input.tsx`: adapted PromptInput, with persona and memory-technique props.
- `lib/utils.ts`: shadcn `cn` helper (clsx + tailwind-merge).
- `index.css`: Tailwind 4 imports, animation utilities and HSL theme tokens.
- `components.json`: shadcn aliases and style configuration.
- `demo.tsx`: standalone gradient demo component with visible submission feedback.
- `main.tsx`: composer entry and event adapter.
- `scripts/build-preview.py`: creates self-contained `dist/preview.html` for the hosted Artifact.

Use `@/components/ui/ai-chat-input` for imports. The project root here is `frontend-preview`, so `/components/ui` means this folder, not the Crew root. Keeping UI primitives here matches shadcn's registry conventions and prevents broken aliases when adding components.

## Build

```sh
npm ci
npm run build
```

The build runs TypeScript checking, Vite bundling, Tailwind generation, and standalone HTML assembly. Open `dist/preview.html` as a local file or publish it as the existing Artifact. No backend, model API key or server is required. `index.html` is the editable workspace template, not the generated output.

React, TypeScript, Tailwind and the shadcn aliases are already configured; no CLI initialization is required. To add a shadcn component later, run `npx shadcn@latest add button` from this directory. For a fresh project elsewhere, use `npm create vite@latest my-app -- --template react-ts`, install `tailwindcss @tailwindcss/vite`, configure the Vite plugin, add an `@/*` alias in TypeScript/Vite, then run `npx shadcn@latest init`.

## Integration changes from the supplied snippet

- Uses supported Tailwind semantic tokens rather than undefined `----color-*` aliases. Destructive foreground values are HSL channels because the theme mapping wraps them in `hsl()`.
- Attachment URLs live until removal, submission or unmount, rather than being revoked whenever the attachment list changes.
- Image removal uses separate keyboard-accessible buttons; gallery has a dialog name, Escape close, focus containment and focus restoration.
- Voice input uses browser speech recognition if available. Permission denial/unsupported APIs show an explicit status. No fabricated transcript is inserted. The hosted sandbox may prohibit microphone access.
- The gallery is portaled outside the composer; preview keeps viewport fitting and independent conversation scrolling.
- The composer is adapted rather than copied verbatim: shared icon and modal code is condensed, animation uses CSS transitions, and visible status replaces console-only demo feedback.
- Persona and memory-technique selectors live inside the composer and update the local preview header/metadata; the duplicate row beneath it was removed. Memory algorithms remain simulated. Image names are included in the local simulated turn; no image analysis or upload occurs.
- Tailwind preflight is omitted to preserve the existing workspace typography and layout. Generated utilities still apply to the component.

Draft messages and files are in-memory and reset on reload. `onSubmit` is synchronous; the host should only enable the composer when ready to accept a message.

## Topology background

`components/ui/topology-field.tsx` exports `TopologyField` and `TOPOLOGY_FIELD_DEFAULTS`. Its public props match the supplied component: `mode`, `hue`, `saturation`, `brightness`, `className`, `style`. `components/ui/topology-field-demo.tsx` preserves the supplied full-screen demo separately from the existing prompt demo.

The chat mounts a light-mode, decorative background at 45% opacity. It does not intercept pointer events or keyboard focus, and is hidden from assistive technology. The supplied 120-node spherical distribution, proximity edges, rotation and pulses are recreated with a native Canvas 2D projection. This deliberately adapts the WebGL/iframe implementation to avoid unreliable GPU rendering in the report host. There are no external asset requests. Hidden marketing markup and external fonts/icons are omitted. This is an adapted integration, not a byte-for-byte copy.

Light mode uses dark lines on the workspace's light surface. Default dark mode remains available for the standalone demo. Animation pauses for reduced-motion preferences, hidden documents and offscreen canvases; ResizeObserver keeps the canvas synchronized with the chat area. An SVG fallback appears if Canvas 2D is unavailable. The animation is decorative and does not visualize live conversation data.

No further shadcn/Tailwind/TypeScript setup is needed. Components live in `components/ui`, styles in `index.css`, aliases in `components.json`, `tsconfig.json` and `vite.config.ts`.

## Light and dark themes

Dark mode uses neutral black surfaces, grayscale text, borders, selection/focus states, topology lines and inspector indicators.

The moon/sun button in the chat header toggles the whole workspace, including the React input, menus, attachment gallery, inspector and topology field. The initial theme follows the system preference unless a saved choice exists. The selected theme is stored in localStorage when the host permits it; sandboxed report hosts can restrict persistence, in which case the switch still works for the current view. Theme tokens and workspace overrides live in `index.css`, with selection helpers in `lib/theme.ts`.

## Integrated backend preview

`npm run build:integrated` produces `dist/integrated.html`, preserving the standalone demo separately. From the repository root, launch `.venv/bin/python -m uvicorn preview_server:app --host 0.0.0.0 --port 20305`. This serves the existing FastAPI application and integrated UI on one origin. The backend's database configuration and model configuration are reused without changing its API implementation.

The integrated controller is `integrated.js`: it loads actual personas and conversations, persists titles/settings, reads SSE incrementally, exports backend data, and loads entity history, graph relationships, summary, and token counters. Chain Studio describes the actual sequential pipeline; it does not offer unsupported pipeline switches. Image attachments are disabled because the API accepts text only. Voice transcription requires browser support and a secure context.

Run `npm run test:live` with the preview running (override `PREVIEW_URL` if needed). It exercises the assembled UI against real HTTP APIs and deletes its own test conversation afterward. Existing `npm test` retains standalone/component coverage.

The preview uses SQLite fallback and retrieves selected Gemini and Groq credentials from the injected environment. The frontend displays the backend stream; configured Gemini failures are shown as errors. A completed response is considered saved only after the backend's `done` event. Aborted/failed partial turns are reconciled with saved history.


Login topology background
-------------------------
The project already supports React, TypeScript, Tailwind v4, and shadcn aliases.
UI components belong in `components/ui/` (`@/components/ui`); shared Tailwind
styles are in `index.css`. Login form styles remain in `../login/slide navbar style.css`.
No additional shadcn setup is required.

`components/ui/topology-field.tsx` provides the supplied iframe-based Three.js
scene and props: mode, hue (-180–180), saturation (0–2), brightness (0.35–1.65),
className, and style. It uses React useMemo, with no provider or shared state.
`components/ui/topology-field-demo.tsx` contains the full-screen demo.
`login-background.tsx` mounts it in dark mode behind the forms. The original
chat background remains in `components/ui/chat-topology-field.tsx`.

Three.js r128 is bundled locally. Hidden presentation markup, stock portraits,
Iconify, and CDN Tailwind are omitted because only the canvas is displayed.
The decorative iframe has script-only sandbox permissions and cannot read the
account session. The scene adapts to its viewport, honors reduced motion,
pauses while hidden, and disposes WebGL resources on exit.

`npm run build:integrated` also builds `../login/assets/login-background.js`.
`npm test` includes form mapping and background document checks. Browser visual
verification is separate from these checks.
