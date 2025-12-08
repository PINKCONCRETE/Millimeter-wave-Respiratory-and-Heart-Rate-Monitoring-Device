import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';
import { createSvgIconsPlugin } from 'vite-plugin-svg-icons';
import { viteMockServe } from 'vite-plugin-mock';

const name = 'MMW Product';

const port = process.env.PORT || 9528;

function resolvePath(dir: string) {
  return path.resolve(__dirname, dir);
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    createSvgIconsPlugin({
      iconDirs: [resolvePath('src/icons')],
      symbolId: 'icon-[name]'
    }),
    viteMockServe({
      // mockPath: 'mock',  // mock文件地址
      // localEnabled: process.env.NODE_ENV === 'development', // 开发环境启用
    }),
  ],
  
  // 基础路径，对应原来的 publicPath
  base: '/',
  
  // 环境变量前缀设置
  envPrefix: 'VITE_',

  // 定义全局常量
  define: {
    'process.env': { 
      NODE_ENV: JSON.stringify(process.env.NODE_ENV),
      BASE_URL: JSON.stringify('/'),
      TITLE: JSON.stringify(name)
    }
  },
  
  // 解析配置
  resolve: {
    alias: {
      '@': resolvePath('src')
    }
  },
  
  // 构建配置
  build: {
    outDir: 'dist', // 输出目录
    assetsDir: 'static', // 静态资源输出目录
    sourcemap: false, // 不生成 sourcemap
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'element-plus': ['element-plus'],
          'echarts': ['echarts'],
        },
        chunkFileNames: 'static/js/[name]-[hash].js',
        entryFileNames: 'static/js/[name]-[hash].js',
        assetFileNames: 'static/[ext]/[name]-[hash].[ext]'
      }
    },
    cssCodeSplit: true,
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: process.env.NODE_ENV === 'production', // 生产环境下移除console
        drop_debugger: process.env.NODE_ENV === 'production'
      }
    }
  },
  
  // 开发服务器配置
  server: {
    host: '0.0.0.0', // 监听所有地址
    port: port as number, // 开发服务器端口
    open: true, // 自动打开浏览器
    cors: true, // 允许跨域
    proxy: {
      '/api': {
        // target: 'http://10.129.189.217:5000',
        target: "http://localhost:5000",
        changeOrigin: true,
        // rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  },
  
  // 预览服务器配置
  preview: {
    port: 9529,
    open: true
  },
  
  // CSS相关配置
  css: {
    preprocessorOptions: {
      scss: {
        // additionalData: `@import "@/styles/variables.scss";` // 如果需要全局引入变量
      }
    },
    modules: {
      localsConvention: 'camelCaseOnly'
    }
  },
  
  // 性能优化
  optimizeDeps: {
    include: [
      'vue', 
      'vue-router',
      'pinia',
      'axios',
      'element-plus',
    ]
  },
  
});