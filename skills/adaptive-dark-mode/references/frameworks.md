# Framework notes

Read only the sections for the stack you found. Syntax changes between major versions, so check the installed version in `package.json`, the `Gemfile`, or the lockfile before applying any of these, and adjust.

The goal is the same in every stack (fix-patterns §1 and §2):
- a **static** `light dark` declaration in the HTML head and on `:root`
- a toggle that only **narrows** it
- dark styles that are active whenever the used scheme is dark, **even before JS runs**

## Contents
- Tailwind CSS v4
- Tailwind CSS v3
- shadcn/ui
- Next.js (+ next-themes)
- SvelteKit (+ mode-watcher)
- Vue / Nuxt (@nuxtjs/color-mode, VueUse)
- Astro
- Rails (ERB, Turbo, tailwindcss-rails)
- Bootstrap 5.3
- MUI
- Chakra UI
- CSS-in-JS (styled-components, Emotion)
- WordPress
- Plain HTML/CSS

---

## Tailwind CSS v4

- **Default `dark:` variant:** `@media (prefers-color-scheme: dark)`. That gives you a dark theme but **no declaration**, so add one:

  ```css
  @import "tailwindcss";
  @layer base { :root { color-scheme: light dark; } }
  ```

  Or put the `scheme-light-dark` utility on `<html>`, if your Tailwind version has the `scheme-*` utilities.

- **Class or attribute toggle** that also respects the system preference before JS runs:

  ```css
  @custom-variant dark {
    &:where(.dark, .dark *) { @slot; }
    @media (prefers-color-scheme: dark) {
      &:where(:not(.light, .light *)) { @slot; }
    }
  }
  @layer base {
    :root { color-scheme: light dark; }
    :root.light { color-scheme: light; }
    :root.dark  { color-scheme: dark; }
  }
  ```

  The common `@custom-variant dark (&:where(.dark, .dark *));` alone is the mismatch trap: system dark with no class gives UA dark surfaces and light utilities.

- **Theme tokens in `@theme`:** define them once with `light-dark()` so utilities like `bg-surface` adapt with no `dark:` duplication:

  ```css
  @theme { --color-surface: light-dark(#fff, #0f1115); --color-ink: light-dark(#14161a, #e7e9ee); }
  ```

- **Hard-coded utilities:** `bg-white` and `text-gray-900` without a `dark:` partner on the same element are the usual leftovers. The audit counts them.

## Tailwind CSS v3

- **`darkMode` unset or `'media'`:** media-query based. Add the declaration in your base CSS:

  ```css
  @layer base { :root { color-scheme: light dark; } }
  ```

- **`'class'` or `'selector'`:** the mismatch trap. Since v3.4.1 a custom variant can combine both:

  ```js
  // tailwind.config.js
  module.exports = {
    darkMode: ['variant', [
      '@media (prefers-color-scheme: dark) { &:not(.light *) }',
      '&:is(.dark *)',
    ]],
  };
  ```

  Pair it with the `:root`, `:root.light`, and `:root.dark` `color-scheme` rules above.

  On older v3, keep `'class'` and make the head script always resolve `.dark` or `.light` before paint (fix-patterns §2, option 2).

## shadcn/ui

- **Tokens:** `globals.css` defines them under `:root` and `.dark`. The Tailwind v4 template uses `@custom-variant dark (&:is(.dark *));`, and theme switching is usually next-themes with `attribute="class"`.
- **Add the declaration and the narrowing rules:**

  ```css
  :root { color-scheme: light dark; }
  .light { color-scheme: light; }
  .dark  { color-scheme: dark; }
  ```

- **Make the dark tokens apply with no JS too** (optional, for robustness). Mirror the `.dark { … }` block inside `@media (prefers-color-scheme: dark) { :root:not(.light) { … } }`. Or convert each token to `light-dark(<:root value>, <.dark value>)` and drop the `.dark` block entirely.
- **Charts:** shadcn charts are Recharts, which is SVG, so they follow CSS variables. Check custom tooltip backgrounds.

## Next.js (+ next-themes)

- **App Router:** declare via the viewport export. Next emits the meta tag.

  ```ts
  // app/layout.tsx
  import type { Viewport } from 'next';
  export const viewport: Viewport = {
    colorScheme: 'light dark',
    themeColor: [
      { media: '(prefers-color-scheme: light)', color: '#ffffff' },
      { media: '(prefers-color-scheme: dark)',  color: '#0f1115' },
    ],
  };
  ```

- **Pages Router:** add `<meta name="color-scheme" content="light dark" />` in `pages/_document.tsx` `<Head>`.
- **next-themes:** use `<ThemeProvider attribute="class" defaultTheme="system" enableSystem>`, with `suppressHydrationWarning` on `<html>`.
  - `enableColorScheme` (on by default) sets `color-scheme` from its inline script. That's fine to keep, but it doesn't replace the static declaration.
  - **`defaultTheme="light"` is a red flag.** First-time visitors with a dark system get the light theme, and Safari converts it.
- **Hydration flicker:** components that render theme-dependent markup (logo variants, icons) from `useTheme()` must render a neutral placeholder until mounted, or use CSS-only switching (fix-patterns §5).

## SvelteKit (+ mode-watcher)

- **Static declaration:** in `src/app.html`, before `%sveltekit.head%`:

  ```html
  <meta name="color-scheme" content="light dark" />
  ```

  Then add `:root { color-scheme: light dark; }` and the `.light`/`.dark` narrowing rules in the global stylesheet.
- **mode-watcher:** `<ModeWatcher defaultMode="system" />` in the root `+layout.svelte`. It toggles the `dark` class from a head script (and may set `color-scheme` from JS as well). Keep the static declaration either way, and use the combined Tailwind variant above if Tailwind is in play.
- **Theme-dependent `<img>` swaps:** use the CSS-only approach so SSR markup is identical for both schemes.
- If your environment has Svelte-specific tooling (for example the official Svelte MCP server), use it when editing `.svelte` files.

## Vue / Nuxt (@nuxtjs/color-mode, VueUse)

- **@nuxtjs/color-mode:** adds `.dark-mode`/`.light-mode` classes by default. Set `colorMode: { classSuffix: '', preference: 'system' }` to get `.dark`/`.light`.
- **Static meta via `nuxt.config`:**

  ```ts
  app: { head: { meta: [{ name: 'color-scheme', content: 'light dark' }] } }
  ```

  Add the `:root` CSS rules in a global stylesheet.
- **VueUse `useDark()`:** client-only. Add the static declaration plus media-query fallbacks so SSR output isn't light-only.

## Astro

- **Declaration:** in the base layout `<head>`, add the meta tag and an `is:inline` script for the toggle. Astro won't bundle or defer `is:inline` scripts, which is what you want for pre-paint.
- **View Transitions / ClientRouter:** re-apply the class on `astro:after-swap`, because the new document's `<html>` replaces the old one's attributes.

## Rails (ERB, Turbo, tailwindcss-rails)

- **Static meta:** in `app/views/layouts/application.html.erb` `<head>`, before `stylesheet_link_tag`:

  ```erb
  <meta name="color-scheme" content="light dark">
  ```

  Check other layouts too (mailer layouts excluded): `admin`, `devise`, and so on.
- **Toggle:** an inline `<script>` in the head (not via importmap, which loads as a module and is deferred) sets the class before paint. A Stimulus controller handles clicks and writes `localStorage`, or a cookie if the server should render the class. With a cookie, render `<html class="<%= theme_class %>">` server-side and you need no head script at all.
- **Turbo Drive:** it keeps the `<html>` element across visits, so the class persists. Inline head scripts don't re-run on Turbo visits.
- **tailwindcss-rails v4:** CSS entry is `app/assets/tailwind/application.css`. Apply the Tailwind v4 notes.
- **Server-rendered emails:** out of scope. Email clients have their own dark-mode behavior.

## Bootstrap 5.3

- **Color modes:** use `data-bs-theme`. `[data-bs-theme=dark]` sets `color-scheme: dark` and the dark variables. The default build has no system detection: the docs' `color-modes.js` resolves "auto" with `matchMedia` and sets the attribute.
- **Add the declaration and narrowing:**

  ```css
  :root { color-scheme: light dark; }
  [data-bs-theme=light] { color-scheme: light; }
  ```

  Then do one of two things:
  - run the color-mode script **inline in `<head>`** and always resolve "auto" to an explicit attribute before paint
  - or compile with `$color-mode-type: media-query` if you don't need a toggle
- **Hard-coded utilities:** `.bg-white`, `.text-dark`, and `.bg-light` don't adapt. Swap them for `.bg-body`, `.bg-body-tertiary`, and `.text-body-emphasis`.

## MUI

- **Theme setup (v6+):**

  ```ts
  createTheme({ colorSchemes: { light: true, dark: true }, cssVariables: { colorSchemeSelector: 'class' } })
  ```

- **No flash:** render `<InitColorSchemeScript attribute="class" />` in the document head for SSR.
- **`<CssBaseline enableColorScheme />`** sets `color-scheme` through injected styles. Still add the static meta tag.
- **Older v5:** `ThemeProvider` with a palette `mode` switched in JS has no pre-paint path, so either migrate to CSS variables or make SSR render the stored mode.

## Chakra UI

- **v2:** use `ColorModeScript` in the document head with `initialColorMode: 'system'`.
- **v3:** uses next-themes under the hood, so apply the next-themes notes.
- **Either version:** add the static meta tag.

## CSS-in-JS (styled-components, Emotion)

Theme objects in JS are invisible to the static audit. Find them (`ThemeProvider`, `createGlobalStyle`, `theme.ts`) and read them.

The robust pattern:
- emit CSS custom properties for both schemes in a global style (with `light-dark()` or media queries)
- have components read `var(--…)` rather than `props.theme.colors.x`

That way SSR markup is correct for both schemes before hydration.

## WordPress

- **Block themes:** `theme.json` has no dark variant built in. Output the declaration only if the theme really has dark styles:

  ```php
  add_action('wp_head', function () {
    echo '<meta name="color-scheme" content="light dark">' . "\n";
  }, 1);
  ```

  Implement the dark palette as CSS custom properties in the theme stylesheet. Test whether your WP version keeps `light-dark()` values if you put them in `theme.json` palettes.
- **Classic themes:** edit `header.php`.
- **Posts and pages:** colors chosen in the editor are inline styles on blocks. The audit can't see database content, so sample real pages with the probe.

## Plain HTML/CSS

Apply fix-patterns §1–§3 directly. If there's no build step, a single `tokens.css` with `light-dark()` values, loaded first, is the least invasive path to A.
