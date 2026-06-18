import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://kashishkapoor.com',
  devToolbar: { enabled: false },
  redirects: {
    '/projects': '/work',
    '/projects/': '/work/',
  },
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
