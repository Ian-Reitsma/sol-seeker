export const API_BASE_URL: string =
  // Vite will replace process.env.VITE_API_URL at build time via define()
  (process.env.VITE_API_URL as string | undefined) || 'http://localhost:8000'

export default API_BASE_URL
