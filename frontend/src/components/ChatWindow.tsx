import { useEffect, useRef, useState } from 'react'
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

export function ChatWindow({ profile, onResponse, visibleJobIds, applyRequest, onApplyRequestHandled }: {
  profile: ResumeProfile | null
  onResponse: (response: ChatResponse) => void
  visibleJobIds: string[]
  applyRequest: { jobId: string; requestId: string } | null
  onApplyRequestHandled: () => void
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([welcome])
  const [activeFilters, setActiveFilters] = useState<ChatFilters>(emptyFilters)
  const [sending, setSending] = useState(false)
  const handledApplyRequest = useRef<string | null>(null)
  const hasStartedChat = messages.some((message) => message.role === 'user')

  useEffect(() => {
    if (!applyRequest || handledApplyRequest.current === applyRequest.requestId) return
    handledApplyRequest.current = applyRequest.requestId
    void sendMessage('Apply to this job', applyRequest.jobId)
    onApplyRequestHandled()
  }, [applyRequest])

  async function sendMessage(text: string, selectedJobId?: string) {
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', text }
    const history: ChatTurn[] = [...messages.filter((message) => message.id !== 'welcome'), userMessage]
      .map(({ role, text: content }) => ({ role, content }))
    setMessages((current) => [...current, userMessage])
    setSending(true)
    try {
      const response = await chatService.send(text, profile, history, activeFilters, visibleJobIds, selectedJobId)
      setActiveFilters(response.active_filters)
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
      </div>
      <div className="conversation-body">
        <MessageList messages={messages} />
        {sending && <div className="chat-typing" role="status">JobFinder is searching…</div>}
        {!hasStartedChat && (
          <div className="workflow-card">
            <div className="workflow-title">Your job search, in five steps</div>
            <ol className="workflow-list">
              <li><span>01</span> Add your resume</li>
              <li><span>02</span> Review profile matches</li>
              <li><span>03</span> Search the job dataset</li>
              <li><span>04</span> Refine results in chat</li>
              <li><span>05</span> Track applications here</li>
            </ol>
            <p className="workflow-note">Ask “apply to job 1” to record an application. JobFinder tracks its status; submit applications on the employer site.</p>
          </div>
        )}
      </div>
      <ChatInput onSend={sendMessage} disabled={sending} />
    </section>
  )
}
