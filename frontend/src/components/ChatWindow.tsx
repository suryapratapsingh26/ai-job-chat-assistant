import { useState } from 'react'
import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'
import type { ChatMessage } from './MessageBubble'
import { chatService, type ChatFilters, type ChatResponse, type ChatTurn, type ResumeProfile } from '../services/api'

const welcome: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  text: 'Welcome. Tell me the role, skills, location, or work style you want. Upload a resume to personalize recommendations, then refine the results here.',
}

const emptyFilters: ChatFilters = { skills: [], location: null, remote: null, role: null, experience_level: null }

export function ChatWindow({ profile, onResponse }: {
  profile: ResumeProfile | null
  onResponse: (response: ChatResponse) => void
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([welcome])
  const [activeFilters, setActiveFilters] = useState<ChatFilters>(emptyFilters)
  const [currentJobIds, setCurrentJobIds] = useState<string[]>([])
  const [sending, setSending] = useState(false)

  async function sendMessage(text: string) {
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', text }
    const history: ChatTurn[] = [...messages.filter((message) => message.id !== 'welcome'), userMessage]
      .map(({ role, text: content }) => ({ role, content }))
    setMessages((current) => [...current, userMessage])
    setSending(true)
    try {
      const response = await chatService.send(text, profile, history, activeFilters, currentJobIds)
      setActiveFilters(response.active_filters)
      setCurrentJobIds(response.jobs.map((job) => job.job_id))
      onResponse(response)
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', text: response.assistant_message }])
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'The assistant could not process that request. Please try again.'
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', text: message }])
    } finally {
      setSending(false)
    }
  }

  return (
    <section className="chat-panel" aria-labelledby="conversation-heading">
      <div className="chat-panel-heading">
        <div>
          <div className="section-eyebrow">YOUR WORKSPACE</div>
          <h1 id="conversation-heading">Let’s find your next role.</h1>
        </div>
        <span className="connection-status"><span /> Job assistant ready</span>
      </div>
      <div className="conversation-body">
        <MessageList messages={messages} />
        {sending && <div className="chat-typing" role="status">Pathfinder is searchingâ€¦</div>}
        <div className="workflow-card">
          <div className="workflow-title">Your job search, in five steps</div>
          <ol className="workflow-list">
            <li><span>01</span> Add your resume</li>
            <li><span>02</span> Review profile matches</li>
            <li><span>03</span> Search the job dataset</li>
            <li><span>04</span> Refine results in chat</li>
            <li><span>05</span> Apply on the employer site</li>
          </ol>
          <p className="workflow-note">Chat searches use the job dataset. Resume matches are personalized; general searches do not use a match score.</p>
        </div>
      </div>
      <ChatInput onSend={sendMessage} disabled={sending} />
    </section>
  )
}
