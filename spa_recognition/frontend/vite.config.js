import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Configura Vite con il plugin React per supportare JSX/TSX.
// VITE_SPA_API_BASE può essere sovrascritto via variabile d'ambiente per puntare
// al backend corretto in sviluppo e in produzione.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});

