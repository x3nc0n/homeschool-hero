# Design

## Theme

**Strategy**: Restrained — tinted neutrals + single blue primary accent. Light mode default; full dark and high-contrast themes provided.

**Register**: Product (task-oriented app, design serves the workflow)

**Personality**: Quiet competence. Calm, trustworthy, functional. No decorative elements; color carries meaning only.

---

## Color Palette

Defined as HSL CSS custom properties in `frontend/src/index.css`. All color tokens flow through Tailwind via `tailwind.config.js`.

### Light mode (`:root`)

| Token | HSL value | Hex approx. | Usage |
|---|---|---|---|
| `--background` | 0 0% 100% | #FFFFFF | Page background |
| `--foreground` | 222.2 84% 4.9% | #0B1121 | Primary text |
| `--card` | 0 0% 100% | #FFFFFF | Card / panel surface |
| `--card-foreground` | 222.2 84% 4.9% | #0B1121 | Text on cards |
| `--primary` | 221.2 83.2% 53.3% | #3B7EF0 | Primary actions, active nav, focus rings |
| `--primary-foreground` | 210 40% 98% | #F5F9FE | Text on primary |
| `--secondary` | 210 40% 96.1% | #EEF3FB | Secondary buttons, muted surfaces |
| `--secondary-foreground` | 222.2 47.4% 11.2% | #1A2847 | Text on secondary |
| `--muted` | 210 40% 96.1% | #EEF3FB | Subdued backgrounds |
| `--muted-foreground` | 215.4 20% 40% | #4D5F78 | Subdued text, captions, placeholders |
| `--accent` | 215 65% 88% | #C0D5F7 | Interactive hover/selection highlight — distinct from secondary |
| `--border` | 214.3 31.8% 91.4% | #DDE4EF | Borders and dividers |
| `--destructive` | 0 84.2% 60.2% | #F05252 | Destructive actions, error states |
| `--ring` | 221.2 83.2% 53.3% | #3B7EF0 | Focus ring (matches primary) |
| `--radius` | 0.65rem | — | Base border-radius |

### Dark mode (`.dark`)

Inverted navy-blue scale. Background `222.2 84% 4.9%` (#0B1121), same primary blue shifted to `217.2 91.2% 59.8%`. Muted surfaces use `217.2 32.6% 17.5%`. Accent `217.2 55% 25%` — more saturated than secondary/muted dark, used for hover/selection surfaces.

### High-contrast (`.theme-high-contrast`)

Pure black background `0 0% 0%`, pure white foreground, yellow accent `55 100% 50%` for focus/ring. WCAG AAA compliant.

---

## Typography

**Family**: `Geist Variable` (variable font, loaded via CDN/package) with Inter and system-ui fallbacks.

**Base heading styles** (applied globally in `@layer base`): `h1–h3` receive `text-wrap: balance` and `letter-spacing: -0.02em`. `p` elements receive `text-wrap: pretty`.

**Scale** (Tailwind defaults, no overrides):
| Step | Class | Size | Usage |
|---|---|---|---|
| xs | `text-xs` | 0.75rem / 12px | Metadata, timestamps, badge labels |
| sm | `text-sm` | 0.875rem / 14px | Body text, descriptions, table rows |
| base | `text-base` | 1rem / 16px | Default prose |
| lg | `text-lg` | 1.125rem / 18px | Sidebar app name, section titles |
| xl | `text-xl` | 1.25rem / 20px | Page headings (mobile) |
| 2xl | `text-2xl` | 1.5rem / 24px | **Page h1 convention**, review detail h2 |

**App convention for page titles**: `<h1 className="text-2xl font-semibold">`. All pages must follow this — `text-3xl` is not a valid page heading size.

**Weights in use**: `font-medium` (500), `font-semibold` (600), `font-bold` (700).

**Line height / spacing**: Tailwind defaults. No explicit `leading-` overrides.

**Notable pattern**: `text-xs uppercase tracking-wide text-muted-foreground` used for nav section labels — small-caps eyebrow style (deprecated per Workstream 3 decisions; sidebar was refactored to flat pinned/collapsed structure).

---

## Spacing

Base unit: 4px (Tailwind default). Custom tokens defined in `:root` (`--space-1` through `--space-6`, 0.25rem–1.5rem) but used only in compact density overrides.

**Dominant patterns observed**:
- `space-y-4` between major page sections
- `gap-3` / `gap-4` for grid and flex layouts
- `p-3` / `p-4` card content padding
- `p-6` empty-state padding

---

## Components

Radix UI primitives via shadcn/ui. Registered in `frontend/components.json`. Key components:

### Card
`data-slot="card"` — default border + shadow-sm. Used for every panel, widget, and detail section. Nested cards exist in practice (submission detail inside upload page — `Card size="sm"` inside `CardContent`).

### Button
Variants: `default` (primary fill), `secondary`, `outline`, `ghost`, `destructive`. Size: `default`, `sm`, `icon`. Hover/active transitions via `180ms ease` theme transitions.

### Input / Select / Textarea
Standard shadcn form controls. Border `--input` token. No floating labels; all labels are stacked above via `<Label>`.

### Badge
Variants: `default` (primary-tinted), `secondary`, `outline`, `destructive`. Used heavily for status indicators throughout.

### Table
shadcn table. Used in ReviewQueuePage. Native `<input type="checkbox">` for row selection (unstyled, inconsistent with the rest of the control vocabulary).

### Tabs
shadcn tabs. Used in GradebookPage to toggle Grades ↔ Review Queue.

### Progress
Radix Progress (single bar). Used in upload and submission detail.

---

## Layout

**App shell**: Left sidebar (260px) + main content, CSS grid. Sidebar sticky, scrollable. Max content width `max-w-7xl`. On mobile: hamburger drawer + bottom tab strip (5 items).

**Page layout pattern**: `space-y-4` vertical stack of Cards. Responsive grids inside cards (`md:grid-cols-2`, `xl:grid-cols-[…]`).

**Breakpoints**: Tailwind defaults (sm 640px, md 768px, lg 1024px, xl 1280px).

**Density system**: `data-density="compact"` attribute on `:root` reduces card padding, button height, and table cell padding via `[data-density='compact']` selectors.

---

## Motion

Theme transitions on body/card/button/input: `background-color 180ms ease, color 180ms ease, border-color 180ms ease, box-shadow 180ms ease`. No page transition animations. No reveal animations. `tailwindcss-animate` installed but minimal use observed beyond Radix open/close.

---

## Current Weaknesses

1. ~~**Accent ≡ Secondary ≡ Muted**~~ **FIXED (Workstream 4)**: `--accent` now `215 65% 88%` (light) / `217.2 55% 25%` (dark) — clearly blue-tinted and distinct from `--secondary`/`--muted`.
2. **No status-color semantic layer**: Status (compliant/warning/critical) is communicated through badge variant only. No named semantic tokens for success/warning/info.
3. ~~**Nav section eyebrows**~~ **FIXED (Workstream 3)**: Flat pinned/collapsed nav; eyebrow labels removed.
4. **Identical card vocabulary**: Every surface — dashboard widgets, submission lists, review detail panels, compliance warnings — uses the same Card at the same density with the same border. No visual priority differentiation.
5. ~~**Muted-foreground contrast**~~ **FIXED (Workstream 4)**: `--muted-foreground` now `215.4 20% 40%` ≈ ~6:1 on white, ~5.6:1 on muted — safely above AA 4.5:1 on both surfaces.
