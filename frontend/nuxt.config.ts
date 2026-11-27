export default defineNuxtConfig({
  compatibilityDate: '2026-11-01',
  devtools: { enabled: false },
  ssr: true,
  nitro: {
    routeRules: {
      '/api/**': { proxy: 'http://backend:8000/api/**' },
    },
  },
  app: {
    head: {
      title: 'Gold Weekly Intelligence',
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
      script: [
        { src: 'https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js', tagPosition: 'head' },
        { src: 'https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js', tagPosition: 'head' },
      ],
    },
  },
})
