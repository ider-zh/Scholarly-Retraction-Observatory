import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],base:'./',server:{watch:{ignored:['**/data/raw/**','**/data/cache/**','**/data/processed/**']}},build:{outDir:'dist',emptyOutDir:true}});
