export const API_BASE_URL: string =
  (process.env.VITE_API_URL as string | undefined) || 'http://localhost:8000';

export default API_BASE_URL;
