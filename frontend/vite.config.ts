import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'

export default defineConfig({
  plugins: [
    frappeui({
      frontendRoute: '/unifonic-inbox',
      // Explicit paths: auto-detection needs an existing public/ folder in the app package.
      buildConfig: {
        outDir: '../unifonic_whatsapp/public/frontend',
        baseUrl: '/assets/unifonic_whatsapp/frontend/',
        indexHtmlPath: '../unifonic_whatsapp/www/unifonic-inbox.html',
      },
    }),
    vue(),
  ],
})
