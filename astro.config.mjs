import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://kashishkapoor.com',
  devToolbar: { enabled: false },
  // Redirects live in public/_redirects (real 301s on Cloudflare Pages).
  markdown: {
    shikiConfig: {
      themes: {
        light: 'vitesse-light',
        dark: 'vitesse-dark',
      },
      defaultColor: false,
    },
  },
});
