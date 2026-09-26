import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: {
    outDir: 'dist',
    rolldownOptions: {
      // librerie in file separati: cambiano di rado, restano in cache del browser tra un deploy e l'altro
      output: {
        codeSplitting: {
          groups: [
            { name: 'chart', test: /node_modules[\/]chart\.js/ },
            { name: 'grid', test: /node_modules[\/]grid-layout-plus/ },
            { name: 'vue', test: /node_modules[\/]@?vue/ },
          ],
        },
      },
    },
  },
})
