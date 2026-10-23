import { useEffect, useState } from 'react'
import { jobService } from '../services/api'
import type { Job, JobPage } from '../types/job'
import { LoadingIndicator } from './LoadingIndicator'

type LoadState = 'loading' | 'success' | 'empty' | 'error'

function JobCard({ job }: { job: Job }) {
  const summary = job.description.length > 220 ? `${job.description.slice(0, 220).trimEnd()}…` : job.description
  return (
    <article className="job-card">
      <div className="job-card-topline">
        <div className="company-monogram" aria-hidden="true">{job.company.slice(0, 1).toUpperCase()}</div>
        <a className="source-link" href={job.source_link} target="_blank" rel="noreferrer" aria-label={`View ${job.title} at source`}>↗</a>
      </div>
      <h3>{job.title}</h3>
      <p className="job-company">{job.company}</p>
      <div className="job-meta">
        <span>⌖ {job.location}</span>
        {job.experience && <span>◷ {job.experience}</span>}
      </div>
      {summary && <p className="job-description">{summary}</p>}
      {job.skills.length > 0 && (
        <ul className="skill-list" aria-label="Skills">
          {job.skills.slice(0, 4).map((skill) => <li key={skill}>{skill}</li>)}
          {job.skills.length > 4 && <li>+{job.skills.length - 4}</li>}
        </ul>
      )}
      <a className="job-apply-link" href={job.source_link} target="_blank" rel="noreferrer">View listing <span aria-hidden="true">→</span></a>
    </article>
  )
}

function LoadingCards() {
  return (
    <LoadingIndicator label="Loading job listings">
      <div className="job-loading">
        {[1, 2, 3].map((item) => <div className="skeleton-card" key={item}><span /><span /><span /><span /></div>)}
      </div>
    </LoadingIndicator>
  )
}

export function JobResults() {
  const [page, setPage] = useState<JobPage | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [loadingMore, setLoadingMore] = useState(false)
  const [moreError, setMoreError] = useState('')

  async function loadJobs(offset = 0) {
    if (offset === 0) {
      setState('loading')
      setError('')
    } else {
      setLoadingMore(true)
      setMoreError('')
    }
    try {
      const result = await jobService.list(offset)
      setPage((current) => offset > 0 && current
        ? { ...result, jobs: [...current.jobs, ...result.jobs] }
        : result)
      if (offset === 0) setState(result.jobs.length ? 'success' : 'empty')
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'Could not load job listings.'
      if (offset === 0) {
        setError(message)
        setState('error')
      } else {
        setMoreError(message)
      }
    } finally {
      if (offset > 0) setLoadingMore(false)
    }
  }

  useEffect(() => { void loadJobs() }, [])

  return (
    <aside className="results-panel" aria-labelledby="jobs-heading">
      <div className="results-heading">
        <div>
          <div className="section-eyebrow">EXPLORE</div>
          <h2 id="jobs-heading">Job listings</h2>
        </div>
        {state === 'success' && <span className="results-count">{page?.total.toLocaleString()} roles</span>}
      </div>
      <p className="results-intro">General opportunities from our job dataset.</p>
      <div className="results-scroll" aria-label="Job listings">
        {state === 'loading' && <LoadingCards />}
        {state === 'error' && (
          <div className="results-message error-state" role="alert">
            <span className="state-icon">!</span>
            <h3>Listings aren’t available</h3>
            <p>{error} Check that the FastAPI server is running, then try again.</p>
            <button type="button" className="text-button" onClick={() => void loadJobs()}>Try again <span aria-hidden="true">↻</span></button>
          </div>
        )}
        {state === 'empty' && (
          <div className="results-message">
            <span className="state-icon">⌕</span>
            <h3>No listings yet</h3>
            <p>The dataset is empty. Add job listings to the backend dataset and refresh.</p>
            <button type="button" className="text-button" onClick={() => void loadJobs()}>Refresh listings <span aria-hidden="true">↻</span></button>
          </div>
        )}
        {state === 'success' && (
          <div className="job-grid">
            {page?.jobs.map((job) => <JobCard key={job.job_id} job={job} />)}
          </div>
        )}
      </div>
      {state === 'success' && page && (
        <div className="results-footer">
          <p className="listings-footnote">Showing {page.jobs.length} of {page.total.toLocaleString()} available listings.</p>
          {moreError && <p className="field-error" role="alert">{moreError}</p>}
          {page.total > page.jobs.length && (
            <button type="button" className="text-button" disabled={loadingMore} onClick={() => void loadJobs(page.jobs.length)}>
              {loadingMore ? 'Loading…' : 'Load more listings'}
            </button>
          )}
        </div>
      )}
    </aside>
  )
}
