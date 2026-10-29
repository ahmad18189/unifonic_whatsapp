import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Inbox from './Inbox.vue'
import './style.css'
const router = createRouter({ history: createWebHistory('/unifonic-inbox'), routes: [{ path: '/:pathMatch(.*)*', component: Inbox }] })
createApp(App).use(router).mount('#app')
