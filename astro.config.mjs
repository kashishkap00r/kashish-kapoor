import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://kashishkapoor.com',
  devToolbar: { enabled: false },
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
