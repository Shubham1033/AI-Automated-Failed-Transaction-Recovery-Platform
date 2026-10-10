import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./tests',use:{baseURL:process.env.E2E_BASE_URL??'http://localhost:5173'},webServer:process.env.CI?undefined:{command:'echo "Start docker compose before E2E"',reuseExistingServer:true}});
