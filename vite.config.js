import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
const slideRoutes = {name: 'slide-routes', configureServer(server) {
  server.middlewares.use((request, response, next) => {
    if (request.url === '/slides/v2' || request.url.startsWith('/slides/v2?')) {
      response.writeHead(302, {Location: request.url.replace('/slides/v2', '/slides/v2/')});
      response.end();
      return;
    }
    if (request.url.startsWith('/slides/v2/')) request.url = request.url.replace('/slides/v2/', '/presentation-v2/').replace(/^\/presentation-v2\/(?=\?|$)/, '/presentation-v2/index.html');
    next();
  });
}};
export default defineConfig({plugins:[slideRoutes,react()],base:'./',server:{watch:{ignored:['**/data/raw/**','**/data/cache/**','**/data/processed/**']}},build:{outDir:'dist',emptyOutDir:true}});
