import { useState } from 'react'
import { BrandMark } from './components/BrandMark'
import { ChatWindow } from './components/ChatWindow'
import { JobResults } from './components/JobResults'
import { ResumeUpload } from './components/ResumeUpload'
import type { ChatResponse, ResumeProfile } from './services/api'

export default function App() {
  const [profile, setProfile] = useState<ResumeProfile | null>(null)
  const [chatResponse, setChatResponse] = useState<ChatResponse | null>(null)
  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href="#main" aria-label="Pathfinder home">
          <BrandMark />
          <span className="brand-name">pathfinder<span className="brand-period">.</span></span>
        </a>
        <div className="header-right">
          <span className="header-label">AI JOB CHAT ASSISTANT</span>
          <span className="avatar-placeholder" aria-label="Your profile">Y</span>
        </div>
      </header>
      <main id="main" className="workspace">
        <div className="primary-column">
          <ChatWindow profile={profile} onResponse={setChatResponse} />
        </div>
        <div className="support-column">
          <ResumeUpload onProfileParsed={setProfile} />
          <JobResults profile={profile} chatResponse={chatResponse} />
        </div>
      </main>
      <footer className="app-footer">
        <span>Built to make your next move clearer.</span>
        <span>Chat results can be general or personalized with your resume.</span>
      </footer>
    </div>
  )
}
