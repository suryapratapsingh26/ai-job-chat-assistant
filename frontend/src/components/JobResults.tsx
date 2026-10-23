import { useEffect, useState } from 'react'
import { jobService, matchingService } from '../services/api'
import type { ChatResponse, JobMatchResponse, JobRecommendation, ResumeProfile } from '../services/api'
import type { Job, JobPage } from '../types/job'
import { LoadingIndicator } from './LoadingIndicator'

type LoadState = 'loading' | 'success' | 'empty' | 'error'

function JobCard({ job, recommendation }: { job: Job; recommendation?: JobRecommendation }) {
  const summary = job.description.length > 220 ? `${job.description.slice(0, 220).trimEnd()}…` : job.description
  return (
    <article className="job-card">
      <div className="job-card-topline">
        <div className="company-monogram" aria-hidden="true">{job.company.slice(0, 1).toUpperCase()}</div>
        {recommendation && <span className="match-score">{recommendation.match_score}% match</span>}
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
      {recommendation && recommendation.matched_skills.length > 0 && (
        <ul className="matched-skills" aria-label="Matched skills">
          {recommendation.matched_skills.slice(0, 5).map((skill) => <li key={skill}>{skill}</li>)}
        </ul>
      )}
      {recommendation && recommendation.match_reasons.length > 0 && (
        <ul className="match-reasons" aria-label="Why this job matches">
          {recommendation.match_reasons.map((reason) => <li key={reason}>{reason}</li>)}
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

export function JobResults({ profile, chatResponse }: { profile: ResumeProfile | null; chatResponse: ChatResponse | null }) {
  const [page, setPage] = useState<JobPage | null>(null)
  const [state, setState] = useState<LoadState>('loading')
  const [error, setError] = useState('')
  const [loadingMore, setLoadingMore] = useState(false)
  const [moreError, setMoreError] = useState('')
  const [recommendations, setRecommendations] = useState<JobMatchResponse | null>(null)
  const [matching, setMatching] = useState(false)
  const [matchError, setMatchError] = useState('')
  const [showMatches, setShowMatches] = useState(false)
  const [showChatResults, setShowChatResults] = useState(false)

  const hasChatResults = Boolean(chatResponse && ['search_jobs', 'refine_jobs', 'explain_job', 'show_jobs'].includes(chatResponse.intent))
  const showingChatResults = showChatResults && hasChatResults

  useEffect(() => {
    setRecommendations(null)
    setMatchError('')
    setShowMatches(false)
    setShowChatResults(false)
  }, [profile])

  useEffect(() => {
    if (hasChatResults) {
      setShowChatResults(true)
      setShowMatches(false)
    }
  }, [chatResponse, hasChatResults])

  async function findMatches() {
    if (!profile) return
    setMatching(true)
    setMatchError('')
    setShowMatches(true)
    setShowChatResults(false)
    try {
      const result = await matchingService.recommend(profile)
      setRecommendations(result)
    } catch (reason) {
      setMatchError(reason instanceof Error ? reason.message : 'Could not find matching jobs.')
    } finally {
      setMatching(false)
    }
  }

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
          <div className="section-eyebrow">
            {showingChatResults ? (chatResponse?.personalized ? 'RESUME MATCHES' : 'GENERAL SEARCH') : showMatches ? 'PERSONALIZED FROM YOUR PROFILE' : 'EXPLORE'}
          </div>
          <h2 id="jobs-heading">{showingChatResults ? 'Chat results' : showMatches ? 'Recommended jobs' : 'Job listings'}</h2>
        </div>
        {showingChatResults && <span className="results-count">{chatResponse?.jobs.length ?? 0} jobs</span>}
        {showMatches && !matching && recommendations && <span className="results-count">{recommendations.total_matches.toLocaleString()} matches</span>}
        {profile && !showMatches && !showingChatResults && <button type="button" className="primary-action" onClick={() => void findMatches()}>Find matching jobs</button>}
        {(showMatches || showingChatResults) && <button type="button" className="text-button" onClick={() => { setShowMatches(false); setShowChatResults(false) }}>All listings</button>}
      </div>
      <p className="results-intro">
        {showingChatResults
          ? chatResponse?.personalized ? 'Ranked resume matches refined by your conversation.' : 'General listings filtered from the existing job dataset. No resume match score is applied.'
          : showMatches ? 'Ranked by skills, role, experience, and relevant resume details.' : 'General opportunities from our job dataset.'}
      </p>
      {showingChatResults && chatResponse && <ActiveFilters filters={chatResponse.active_filters} />}
      <div className="results-scroll" aria-label="Job listings">
        {!showMatches && !showingChatResults && state === 'loading' && <LoadingCards />}
        {showMatches && matching && <LoadingIndicator label="Finding jobs that fit your profile"><div className="match-loading-space" /></LoadingIndicator>}
        {showMatches && !matching && matchError && (
          <div className="results-message error-state" role="alert">
            <span className="state-icon">!</span>
            <h3>Recommendations aren’t available</h3>
            <p>{matchError}</p>
            <button type="button" className="text-button" onClick={() => void findMatches()}>Try again <span aria-hidden="true">↻</span></button>
          </div>
        )}
        {showMatches && !matching && !matchError && recommendations?.recommendations.length === 0 && (
          <div className="results-message">
            <span className="state-icon">⌕</span>
            <h3>No matching jobs found</h3>
            <p>Try a resume with more role or skill details to find relevant listings.</p>
          </div>
        )}
        {showMatches && !matching && !matchError && recommendations && recommendations.recommendations.length > 0 && (
          <div className="job-grid">
            {recommendations.recommendations.map((recommendation) => (
              <JobCard key={recommendation.job.job_id} job={recommendation.job} recommendation={recommendation} />
            ))}
          </div>
        )}
        {showingChatResults && chatResponse?.jobs.length === 0 && (
          <div className="results-message">
            <span className="state-icon">⌕</span>
            <h3>No jobs found</h3>
            <p>{chatResponse.assistant_message}</p>
          </div>
        )}
        {showingChatResults && chatResponse && chatResponse.recommendations.length > 0 && (
          <div className="job-grid">
            {chatResponse.recommendations.map((recommendation) => (
              <JobCard key={recommendation.job.job_id} job={recommendation.job} recommendation={recommendation} />
            ))}
          </div>
        )}
        {showingChatResults && chatResponse && !chatResponse.personalized && chatResponse.jobs.length > 0 && (
          <div className="job-grid">
            {chatResponse.jobs.map((job) => <JobCard key={job.job_id} job={job} />)}
          </div>
        )}
        {!showMatches && !showingChatResults && state === 'error' && (
          <div className="results-message error-state" role="alert">
            <span className="state-icon">!</span>
            <h3>Listings aren’t available</h3>
            <p>{error} Check that the FastAPI server is running, then try again.</p>
            <button type="button" className="text-button" onClick={() => void loadJobs()}>Try again <span aria-hidden="true">↻</span></button>
          </div>
        )}
        {!showMatches && !showingChatResults && state === 'empty' && (
          <div className="results-message">
            <span className="state-icon">⌕</span>
            <h3>No listings yet</h3>
            <p>The dataset is empty. Add job listings to the backend dataset and refresh.</p>
            <button type="button" className="text-button" onClick={() => void loadJobs()}>Refresh listings <span aria-hidden="true">↻</span></button>
          </div>
        )}
        {!showMatches && !showingChatResults && state === 'success' && (
          <div className="job-grid">
            {page?.jobs.map((job) => <JobCard key={job.job_id} job={job} />)}
          </div>
        )}
      </div>
      {!showMatches && !showingChatResults && state === 'success' && page && (
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

function ActiveFilters({ filters }: { filters: ChatResponse['active_filters'] }) {
  const values = [
    ...filters.skills,
    filters.location,
    filters.remote === true ? 'Remote' : filters.remote === false ? 'Onsite' : null,
    filters.role,
    filters.experience_level ? `${filters.experience_level} level` : null,
  ].filter((value): value is string => Boolean(value))
  if (!values.length) return null
  return <ul className="result-filter-list" aria-label="Active search filters">{values.map((value) => <li key={value}>{value}</li>)}</ul>
}
