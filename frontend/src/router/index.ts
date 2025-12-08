import { createRouter, createWebHashHistory, createWebHistory, type RouteRecordRaw } from 'vue-router'


/**
 * constantRoutes
 * a base page that does not have permission requirements
 * all roles can be accessed
 */
export const constantRoutes: Array<RouteRecordRaw> = [

  {
    
    path: '/monitor/:userId',
    component: () => import('@/views/Monitor.vue'),
    // hidden: true
  },
  {
    name: '404',
    path: '/404',
    component: () => import('@/views/404.vue'),
    // hidden: true
  },

  {
    path: '/',
    redirect: '/monitor/0',
  },

  // 404 page must be placed at the end !!!
  { path: '/:pathMatch(.*)*', redirect: '/404', meta: { hidden: true } }
]

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: constantRoutes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 如果目标路径是 /show/show，则打开 /big_screen 页面
  if (to.path === '/show/show') {
    window.open('#/big_screen', '_blank'); // 打开新的窗口
    next(false); // 阻止默认跳转，避免继续导航到 /nested
  } else {
    next(); // 执行默认的路由跳转
  }
})

// 重置路由方法
export function resetRouter() {
  const newRouter = createRouter({
    history: createWebHashHistory(),
    scrollBehavior: () => ({ top: 0 }),
    routes: constantRoutes
  })
  // @ts-ignore: Unreachable code error
  router.matcher = newRouter.matcher // reset router
}

export default router