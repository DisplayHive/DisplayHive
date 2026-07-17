import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/DashboardView.vue'),
    },
    {
      path: '/devices',
      name: 'devices',
      component: () => import('../views/DevicesView.vue'),
    },
    {
      path: '/content',
      name: 'content',
      component: () => import('../views/ContentView.vue'),
    },
    {
      path: '/contenttypes',
      name: 'contenttypes',
      component: () => import('../views/ContentTypesView.vue'),
    },
    {
      path: '/templates',
      name: 'templates',
      component: () => import('../views/TemplatesView.vue'),
    },
    {
      path: '/magictags',
      name: 'magictags',
      component: () => import('../views/MagicTagsView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue'),
    },
    {
      path: '/logger',
      name: 'logger',
      component: () => import('../views/LoggerView.vue'),
    },
    {
      path: '/media',
      name: 'media',
      component: () => import('../views/MediaView.vue'),
    },
    {
      path: '/matrix',
      name: 'matrix',
      component: () => import('../views/MatrixView.vue'),
    },
    {
      path: '/screens',
      name: 'screens',
      component: () => import('../views/ScreensView.vue'),
    },
    {
      path: '/screengroups',
      name: 'screengroups',
      component: () => import('../views/ScreenGroupsView.vue'),
    },
    {
      path: '/demo',
      name: 'demo',
      component: () => import('../views/DemoModeView.vue'),
    },
    {
      path: '/importexport',
      name: 'importexport',
      component: () => import('../views/ImportExportView.vue'),
    },
    {
      path: '/pretalx',
      name: 'pretalx',
      component: () => import('../views/PretalxView.vue'),
    },
    {
      path: '/alerting',
      name: 'alerting',
      component: () => import('../views/AlertingView.vue'),
    },
    {
      path: '/users',
      name: 'users',
      component: () => import('../views/UsersView.vue'),
    },
    {
      // Merged into the Accounts/Groups tabs on /users.
      path: '/rights',
      redirect: '/users',
    },
  ],
})

export default router
