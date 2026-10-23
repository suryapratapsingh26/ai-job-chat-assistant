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

export interface ResumeProfile {
  name: string | null
  email: string | null
  phone: string | null
  designation: string | null
  skills: string[]
  experience: string | null
  education: string[]
  projects: string[]
}

export const resumeService = {
  async parse(file: File): Promise<ResumeProfile> {
    const form = new FormData()
    form.append('file', file)
    let response: Response
    try {
      response = await fetch(`${API_BASE_URL}/api/resume/parse`, {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: form,
      })
    } catch {
      throw new Error('Could not reach the resume service. Check that the API is running and try again.')
    }
    const payload = await response.json().catch(() => null) as
      | { profile?: ResumeProfile; detail?: unknown }
      | null
    if (!response.ok) {
      const message = typeof payload?.detail === 'string'
        ? payload.detail
        : `Resume processing failed (${response.status}). Check the file and try again.`
      throw new Error(message)
    }
    if (!payload?.profile) {
      throw new Error('The server returned an incomplete profile. Please try uploading the resume again.')
    }
    return payload.profile
  },
}
