# Design system

The web app (`apps/web`) is one orange accent on a near-white page, 1px
hairlines at the column edges, mono numbered section tags and small, quick
motion. Light and dark follow the system setting.

Values live in the files below. This document names the token or class, says
what it is for and points at the file for the number.

| File                                     | Holds                                                     |
| ---------------------------------------- | --------------------------------------------------------- |
| `apps/web/src/lib/styles/fonts.css`      | Font imports and the fallback face                        |
| `apps/web/src/lib/styles/tokens.css`     | Colour, shadow, easing and layout variables               |
| `apps/web/src/lib/styles/typography.css` | The `t-*` type classes                                    |
| `apps/web/src/lib/styles/base.css`       | Body defaults, selection, focus, reduced motion           |
| `apps/web/src/routes/layout.css`         | Tailwind theme, `.control`, `.column`, `.gutter`, `.band` |
| `apps/web/src/lib/components/`           | Shell, page and section components                        |
| `apps/web/src/lib/components/ui/`        | Controls and status marks                                 |

Component styles live in each component's own `<style>` block. Pages pass
Tailwind utilities only for heights and widths.

## Fonts

The sans face is Inter (`--font-sans`). The mono face is Geist Mono
(`--font-mono`). Both are bundled variable fonts with `font-display: swap`.

`Inter Fallback` is a local Arial-metric face scaled to Inter's width and
vertical metrics. It sits after Inter in `--font-sans`, so text laid out before
Inter loads has Inter's line breaks and the swap moves no line. It lists
Liberation Sans and Arimo as well, for hosts without Arial.

Weights are 400 for body, 450 for labels and 500 for titles and mono emphasis.

## Colour

All colour is a CSS variable on `:root` in `tokens.css`. The dark values sit
under `@media (prefers-color-scheme: dark)`. There is no manual switch.

| Token                                  | Role                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------- |
| `--background-base`                    | Page canvas                                                               |
| `--surface`                            | Cards, inputs, menus                                                      |
| `--ink`                                | Text                                                                      |
| `--ink-alpha-N`                        | Ink at N percent: secondary text, fills, hover and press states           |
| `--border-faint`                       | Rails, rules, row separators                                              |
| `--border-muted`                       | Avatar and key cap borders                                                |
| `--control-border`, `-hover`           | Input borders, strong enough to be a 3:1 edge                             |
| `--heat-100`                           | Accent fills and marks. Never text: it does not reach 4.5:1 on the canvas |
| `--heat-12`, `-20`, `-24`              | Focus halo, selection, progress track                                     |
| `--heat-ink`                           | Accent text, links, focus ring                                            |
| `--button-primary-fill`, `-shadow`     | Primary button                                                            |
| `--ok`                                 | Success mark                                                              |
| `--danger`, `--danger-soft`            | Error mark, text and tint                                                 |
| `--warn`, `--warn-soft`, `--warn-line` | Warning text, tint and edge                                               |
| `--surface-shadow`                     | The sign-in card                                                          |
| `--menu-shadow`                        | The account menu                                                          |

Secondary text is `--ink-alpha-64`. Selection is `--heat-20` with `--heat-ink`
text. The map keeps its light tile style in dark mode.

Text pairs reach 4.5:1 and marks and control edges reach 3:1, in both themes.
Ratios computed from `tokens.css`, with alpha colours composited on their
background:

| Pair                          | Light | Dark  | Needs |
| ----------------------------- | ----- | ----- | ----- |
| ink on canvas                 | 14.37 | 16.87 | 4.5   |
| ink on surface                | 15.13 | 15.55 | 4.5   |
| ink 64% on canvas             | 4.56  | 7.29  | 4.5   |
| ink 64% on surface            | 4.65  | 6.99  | 4.5   |
| `--heat-ink` on canvas        | 4.95  | 5.97  | 4.5   |
| `--heat-ink` on surface       | 5.21  | 5.51  | 4.5   |
| white on primary fill         | 4.55  | 4.55  | 4.5   |
| `--ok` on canvas              | 4.81  | 10.58 | 3     |
| `--danger` on canvas          | 5.44  | 7.44  | 3     |
| `--danger` on `--danger-soft` | 4.83  | 5.98  | 4.5   |
| `--warn` on `--warn-soft`     | 5.88  | 9.48  | 4.5   |
| control border on surface     | 3.67  | 4.49  | 3     |

## Type

The `t-*` classes in `typography.css` are the whole scale. Each sets size, line
height, tracking and weight, and the larger ones step down below 996px.

| Class                      | Use                                       |
| -------------------------- | ----------------------------------------- |
| `t-h4`                     | Page titles                               |
| `t-h5`                     | Section and card titles                   |
| `t-body-lg`                | Descriptions                              |
| `t-body-md`, `t-body-sm`   | Body copy, hints, table text              |
| `t-label-lg`, `-md`, `-xs` | Buttons, links, field labels, brand       |
| `t-mono-sm`, `t-mono-xs`   | Section tags, codes, figures (Geist Mono) |

`body` sets the default size and line height, antialiased smoothing and
`optimizeLegibility`. Numbers use `.num` (tabular figures) so columns and
changing values do not jitter. Header links and buttons keep the 14px label size
below 996px so the row fits a 390px screen.

## Layout

- **Column.** `.column` is `min(100% - 32px, var(--container-width))`, centred.
  The width is fluid at every breakpoint.
- **Gutters.** `.gutter` pads content; the amount grows at 640px and 996px
  (`layout.css`).
- **Rails.** `PageRails` draws two fixed, viewport-tall `--border-faint` lines
  at the column's edges, under the header and above the page, with
  `pointer-events: none`.
- **Bands.** A `.band` is a strip with top and bottom hairlines and a -1px top
  margin, so neighbouring hairlines draw one line.
- **Connectors.** Where a full-width rule meets a rail, a plus-shaped
  `CornerConnector` marks the joint. `CornerArcs` rounds the four inner corners
  of a section tag.
- **Header.** `Header` is fixed and a spacer of height `--header-height` holds
  its place. From 996px the bar is `--header-height` tall at the top and 72px
  once the page is scrolled 8px; below 996px it is 72px. Items are centred in a
  fixed height, so the bar is the same height with or without the "Nueva
  simulación" button. The bottom rule spans the viewport. The spacer is
  constant, so compacting moves nothing below it.
- **Page header.** `PageHeader` holds an optional back link, the `t-h4` title,
  an optional `t-body-lg` description and optional actions. It ends in a
  full-width rule with two connectors.
- **Section tag.** `SectionLabel` is an `h2` band in mono: a `--heat-100`
  marker, `[ 01 / 02 ] ·` with the index in `--heat-ink`, then the title in
  uppercase.
- **Scroll.** `html` has `scroll-padding-top: var(--header-offset)` and smooth
  scrolling, so anchors land below the header.

## Shape

| Element                         | Radius |
| ------------------------------- | ------ |
| Buttons, inputs (`.control`)    | 10px   |
| Header items, menu rows, avatar | 8px    |
| Menu, alerts, map frame         | 12px   |
| Sign-in card                    | 20px   |

Interactive targets are 44px high below 768px and 32 to 36px from 768px:
buttons, inputs, disclosure triggers and menu rows are 36px; header links, the
brand and the avatar are 32px. A control whose look is smaller than its target
pads the hit area and keeps its look.

## Motion

Triggers fire on input (hover, press, open, navigation) or on a state change.
Nothing animates on page load, and nothing is driven by scroll position except
the header's height. Animations use `opacity`, `transform` and `filter`, with
three exceptions: the progress fill's `width` (inside a fixed-size track), the
disclosure's `grid-template-rows` (it opens on a click, which the user caused)
and the fixed header's `height` (out of flow).

Hover and press feedback is quick (a fraction of a second); opening a panel is
slower. The owning component sets each duration. Easing curves are the
`--ease-*` tokens.

| Name               | Trigger                                          | What moves                                       | Owner                |
| ------------------ | ------------------------------------------------ | ------------------------------------------------ | -------------------- |
| Button press       | Pointer down                                     | The button scales down slightly                  | `ui/Button`          |
| Button hover       | Hover                                            | Fill, shadow, sheen opacity                      | `ui/Button`          |
| Link and row hover | Hover                                            | Colour and background                            | pages, `Header`      |
| Row arrow          | Row hover                                        | Arrow shifts 2px                                 | `ui/ArrowIcon`, list |
| Header compact     | Scroll past 8px (996px and up)                   | Header height                                    | `Header`             |
| Header item        | Hover, press                                     | Background, colour, slight scale on press        | `Header`             |
| Menu               | Open                                             | Opacity and a short slide down                   | `Header`             |
| Disclosure         | Click                                            | Panel height (`--ease-disclosure`), chevron turn | `ui/Disclosure`      |
| Progress fill      | Progress update                                  | Fill width (`--ease-spring-snap`)                | simulation page      |
| Content swap       | The first-arrival line changes                   | Opacity, blur and a short slide in               | new-simulation page  |
| Dot spinner        | A job is queued or running, or data is loading   | 12 dots flash in turn                            | `ui/DotSpinner`      |
| Shimmer            | The estimate is loading, or progress has no step | Gradient position                                | pages                |
| Navigation sweep   | A route change is pending                        | A bar crosses a thin track (`--ease-panel`)      | `+layout.svelte`     |
| Estimate stale     | Inputs change while the old estimate shows       | Estimate fades                                   | new-simulation page  |

### Reduced motion

`base.css` has one `prefers-reduced-motion: reduce` block. It cuts every
animation and transition to one instant frame and turns off smooth scroll. Three
components show a still frame instead:

- `DotSpinner` holds all dots at a visible opacity.
- The navigation bar is a full-width static bar.
- The shimmer bars and the indeterminate progress fill stop on a plain fill.

### No layout shift

- The header is fixed and its spacer is constant (see Layout).
- The "Calculando…" note on the new-simulation page is absolutely positioned and
  the estimate section has a minimum height, so the result does not move when it
  arrives.
- A status mark and the spinner have the same footprint, so a list row does not
  move when a job starts.
- The map frame has a fixed height, and its loading overlay is inside it.
- The ASCII field is deterministic, so the server and the browser print the same
  text.
- Fonts swap through `Inter Fallback`, which has Inter's width.

## Components

`apps/web/src/lib/components/`:

| Component                       | Purpose                                                                                                                                                                                                                                              |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Header`                        | Fixed bar: brand, Simulaciones, Nueva simulación (hidden on `/new`) and the account menu (bits-ui dropdown)                                                                                                                                          |
| `PageRails`                     | Fixed rails at the column edges                                                                                                                                                                                                                      |
| `PageHeader`                    | Page title, description, back link, actions, rule and connectors                                                                                                                                                                                     |
| `SectionLabel`                  | Numbered mono tag for a section                                                                                                                                                                                                                      |
| `CornerArcs`, `CornerConnector` | Rail and rule joints                                                                                                                                                                                                                                 |
| `AuthShell`                     | Centred card for sign-in and sign-up, with the footer link outside it                                                                                                                                                                                |
| `AsciiField`                    | Decorative `<pre aria-hidden>` in `--heat-100`, drawn from a shape function. A cell shows a glyph with probability equal to its density, from a ramp of increasingly dense glyphs, using an integer hash so it is deterministic. Used on error pages |
| `ErrorState`                    | Error code in mono, `t-h4` title, message, actions, with an `AsciiField` wave                                                                                                                                                                        |
| `Map`                           | MapLibre map in a framed box; loading overlay with a spinner; failure message                                                                                                                                                                        |
| `ArrivalTable`                  | Port, arrival, UTC time and distance; mono tabular figures, hairline rows                                                                                                                                                                            |
| `SourceDetails`                 | Source parameters in a `Disclosure`                                                                                                                                                                                                                  |

`apps/web/src/lib/components/ui/`:

| Component    | Purpose                                                                                                                                                             |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Button`     | `primary`, `secondary`, `tertiary`; link or button; primary has the sheen layer                                                                                     |
| `Field`      | Label, control, hint and error with `aria-describedby` and `aria-invalid`                                                                                           |
| `Alert`      | `info`, `warning`, `error`: hairline box, a marker on the left edge in the tone's colour. Error uses `role="alert"`, the others `role="status"`                     |
| `Status`     | Job state: `DotSpinner` while active, otherwise a square in the tone's colour, then the label                                                                       |
| `Disclosure` | Button with `aria-expanded` and a panel that is `inert` while closed. `variant` is `row` (top rule, for lists) or `inset` (no rule, for use inside another surface) |
| `DotSpinner` | The 12-dot flash loader                                                                                                                                             |
| `ArrowIcon`  | Arrow glyph used by rows and downloads                                                                                                                              |

The alert, status and field patterns follow the same hairline, radius and marker
language as the rest of the system.

## Screens

- **Sign-in and sign-up.** `AuthShell` card on the rails.
- **Simulations.** `PageHeader`, then one row per simulation: magnitude and
  coordinates, the state or progress line, `Status`, the age, and an arrow. Rows
  are links with a hover fill. A shortcut hint for the `N` key shows from 768px.
  An empty list redirects to `/new`, so the page has no empty state.
- **New simulation.** `PageHeader`; below it the form column (`SectionLabel` 01
  "Sismo", the fields; `SectionLabel` 02 "Estimado", the estimate) and the map
  column, which is sticky from 996px. The submit bar is sticky at the bottom of
  the form column. The estimate shows a skeleton while loading, a fading stale
  state while recalculating, and an `Alert` with a retry on failure.
- **Simulation.** `PageHeader` with a back link, the magnitude and muted
  coordinates, the event description, and `Status` plus the repeat action.
  Alerts for failure carry a "Detalle técnico" `Disclosure`. Running jobs show
  "Avance" with the step and a progress bar. Completed jobs show "Resultados"
  (files as rows, others in a `Disclosure`), the arrivals table, the source
  parameters and the map.
- **Errors.** `ErrorState` for 404 and other failures, inside and outside the
  signed-in shell.

## Accessibility

- Text meets 4.5:1 and marks and control edges 3:1 in both themes (see Colour).
- `:focus-visible` is a 2px `--heat-ink` outline with a 2px offset on every
  element. Inputs add a `--heat-12` halo.
- Focus order follows the DOM. In the signed-in shell the skip link is the first
  focusable element and leads to `#contenido`.
- Both progress bars are `role="progressbar"`: the navigation bar is labelled
  "Cargando" and the job bar "Avance de la simulación".
- Decorative layers (`PageRails`, connectors, arcs, the ASCII field, sheen,
  markers) are `aria-hidden`.
- State is never colour alone: `Status` always prints the label.
- Interactive targets are 44px high below 768px (see Shape).
