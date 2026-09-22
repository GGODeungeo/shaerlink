import { defineConfig } from '@apps-in-toss/web-framework/config';

export default defineConfig({
  appName: 'hidden-deals',
  brand: {
    primaryColor: '#191f28',
  },
  navigationBar: {
    withTitle: true,
  },
  permissions: [],
  webBundleDir: 'dist',
});
