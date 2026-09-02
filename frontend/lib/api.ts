export function getApiUrl(): string {
  if (typeof window !== "undefined") {
    return `${window.location.origin}/api/v1`;
  }
  if (process.env.INTERNAL_BACKEND_URL) {
    return `${process.env.INTERNAL_BACKEND_URL}/api/v1`;
  }
  return "http://backend:8000/api/v1";
}
