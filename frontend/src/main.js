// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory, RouterView } from 'vue-router'

import './theme'
import { ready } from './i18n'
import SalesRepView from './views/SalesRepView.vue'
import './styles.css'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      component: SalesRepView,
      children: [
        { path: 'quotations', name: 'rep-quotations', meta: { repPage: 'quotations' } },
        { path: 'invoices', name: 'rep-invoices', meta: { repPage: 'invoices' } },
        { path: 'activity', name: 'rep-activity', meta: { repPage: 'activity' } },
      ],
    },
    {
      path: '/till',
      component: () => import('./App.vue'),
      children: [
        { path: '', component: () => import('./views/SellView.vue') },
        { path: '/history', component: () => import('./views/HistoryView.vue') },
        { path: '/customers', component: () => import('./views/CustomersView.vue') },
        { path: '/holds', component: () => import('./views/HoldsView.vue') },
        { path: '/register', component: () => import('./views/RegisterView.vue') },
        { path: '/insights', component: () => import('./views/InsightsView.vue') },
        { path: '/settings', component: () => import('./views/SettingsView.vue') },
        { path: '/labels', component: () => import('./views/LabelsView.vue') },
        { path: '/count', component: () => import('./views/StockCountView.vue') },
        { path: '/display', component: () => import('./views/CustomerDisplayView.vue') },
      ],
    },
  ],
})

ready.finally(() => createApp({ render: () => h(RouterView) }).use(createPinia()).use(router).mount('#app'))
