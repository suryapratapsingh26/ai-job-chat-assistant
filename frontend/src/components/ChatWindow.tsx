import { useState } from 'react'
import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'
import type { ChatMessage } from './MessageBubble'

const welcome: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  text: 'Welcome. I can help you explore the job listings in this workspace. Resume understanding and assistant replies are not connected yet, so nothing here is personalized.',
}

export function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([welcome])

  function sendMessage(text: string) {
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', text }
    const statusMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      text: 'Your message is visible in this conversation, but an assistant service is not connected yet. No job search or filtering was performed.',
    }
    setMessages((current) => [...current, userMessage, statusMessage])
  }

  return (
    <section className="chat-panel" aria-labelledby="conversation-heading">
      <div className="chat-panel-heading">
        <div>
          <div className="section-eyebrow">YOUR WORKSPACE</div>
          <h1 id="conversation-heading">Let’s find your next role.</h1>
        </div>
        <span className="connection-status"><span /> Listings connected</span>
      </div>
      <div className="conversation-body">
        <MessageList messages={messages} />
        <div className="workflow-card">
          <div className="workflow-title">Your job search, in five steps</div>
          <ol className="workflow-list">
            <li><span>01</span> Add your resume</li>
            <li><span>02</span> Understand your profile</li>
            <li><span>03</span> Discover relevant jobs</li>
            <li><span>04</span> Refine results in conversation</li>
            <li><span>05</span> Apply with your assistant</li>
          </ol>
          <p className="workflow-note">Resume processing and assistant features will arrive in a later step. For now, browse the general listings.</p>
        </div>
      </div>
      <ChatInput onSend={sendMessage} />
    </section>
  )
}
