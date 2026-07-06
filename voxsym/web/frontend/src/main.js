import { App } from './ui/App.js';

document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('app');
  if (!root) return;
  const app = new App(root);
  app.mount();
});
