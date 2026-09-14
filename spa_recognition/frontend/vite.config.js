import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Configura Vite con il plugin React per supportare JSX/TSX.
// VITE_SPA_API_BASE può essere sovrascritto via variabile d'ambiente per puntare
// al backend corretto in sviluppo e in produzione.
// VITE_BASE_PATH va impostata solo per il deploy su GitHub Pages (project site,
// servito da /<repo>/); il default "/" lascia invariati Docker e sviluppo locale.
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE_PATH || "/",
  server: {
    port: 5173,
  },
});

