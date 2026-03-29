import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  base: '/static/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // 不用 rollup 打包 HTML，只处理静态资源
    rollupOptions: {
      input: {
        // 入口：合并所有 JS 为一个 bundle
        app: './js/main.js',
      },
      output: {
        entryFileNames: 'js/[name].min.js',
        chunkFileNames: 'js/[name]-[hash].js',
        assetFileNames: '[name][extname]',
      },
    },
    minify: 'esbuild',
    sourcemap: false,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8263',
    },
  },
});
