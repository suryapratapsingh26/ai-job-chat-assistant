import { useEffect, useRef, useState } from 'react'
import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'
import type { ChatMessage } from './MessageBubble'
import { chatService, type ChatFilters, type ChatResponse, type ChatTurn, type ResumeProfile } from '../services/api'

const welcome: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  text: 'Welcome. Upload a PDF or DOCX resume to see your profile and personalized job recommendations. Then refine your matches here in chat.',
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
      </div>
      <ChatInput onSend={sendMessage} disabled={sending} />
    </section>
  )
}
