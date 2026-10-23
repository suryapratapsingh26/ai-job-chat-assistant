import type { JobPage } from '../types/job'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw new Error(`The server returned ${response.status}. Please try again.`)
  }
  return response.json() as Promise<T>
}

export const jobService = {
  list: (offset = 0, limit = 24) =>
    getJson<JobPage>(`/api/jobs?offset=${offset}&limit=${limit}`),
}