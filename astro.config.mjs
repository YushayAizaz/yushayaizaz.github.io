import { defineConfig } from 'astro/config';

const configuredSite = process.env.SITE_URL?.trim();
if (configuredSite && !/^https:\/\/[^/]+\/?$/.test(configuredSite)) {
  throw new Error('SITE_URL must be an HTTPS origin without a path.');
}

export default defineConfig({
  ...(configuredSite ? { site: configuredSite } : {}),
  output: 'static',
  trailingSlash: 'always',
  build: { format: 'directory' },
  markdown: { shikiConfig: { theme: 'github-dark' } },
  integrations: [{
    name: 'editorial-draft-boundary',
    hooks: {
      'astro:config:setup': ({ command, config, updateConfig }) => {
        // Unlike NODE_ENV/DEV, this cannot be enabled by build --mode development.
        updateConfig({ vite: { define: {
          __EDITORIAL_DEV_SERVER__: JSON.stringify(command === 'dev'),
          __EDITORIAL_PUBLIC_DIR_URL__: JSON.stringify(config.publicDir.href),
        } } });
      },
    },
  }],
});
