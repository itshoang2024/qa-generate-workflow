# QA Generate Workflow — Design System v1

## Brand
- Product name: SUN.RISER QA Workflow
- Tone: enterprise dev tool, dense data, no marketing fluff
- Inspiration: Linear / Vercel dashboard / GitHub Projects

## Palette (Tailwind tokens)
- Background: slate-950 (dark default) / white (light)
- Surface: slate-900 / slate-50
- Border: slate-800 / slate-200
- Text primary: slate-50 / slate-900
- Text muted: slate-400 / slate-500
- Accent: indigo-500 (links, primary buttons)
- Lane badges:
  - AUTO: emerald-500/15 bg + emerald-400 text
  - BATCH: amber-500/15 bg + amber-400 text
  - BLOCK: rose-500/15 bg + rose-400 text
- Severity badges:
  - S1: rose-500/15 bg + rose-300 text (critical)
  - S2: amber-500/15 bg + amber-300 text
  - S3: slate-500/15 bg + slate-300 text
- Sync phase tags: violet-500/15 bg + violet-300 text
- DeltaStatus: NEW=emerald, MODIFIED=amber, UNCHANGED=slate, REMOVED=rose

## Layout
- Sidebar fixed 256px left, sections: Projects, Runs, HIL Queues, Settings
- Top header 56px: provider status badges + sign-off button + user menu
- Content max-width 1440px, padding 24px

## Typography
- Headings: Inter, font-semibold
- Body: Inter, text-sm default
- Code/IDs: JetBrains Mono, text-xs, slate-400

## Density
- Tables: row height 40px, cell padding 12px x, 8px y
- Cards: padding 16px, border + shadow-sm
- All IDs (run_xxx, feat_xxx, F-001) display as monospace inline chips

## Empty / loading / error states
- Loading: skeleton blocks, not spinners
- Empty: centered icon + headline + CTA
- Error: red banner top of content area, retry button