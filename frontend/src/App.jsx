import { useState, useEffect, useRef } from 'react'
import Header from './components/Header'
import MessageList from './components/MessageList'
import ChatInput from './components/ChatInput'
import SettingsModal from './components/SettingsModal'
import ProjectPanel from './components/ProjectPanel'
import SessionList from './components/SessionList'

const API_BASE = '/api'

function App() {
  const [currentProject, setCurrentProject] = useState(null)
  const [projects, setProjects] = useState([])
  const [currentSession, setCurrentSession] = useState(null)
  const [sessions, setSessions] = useState([])
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showProjects, setShowProjects] = useState(true)
  const [showSessions, setShowSessions] = useState(false)
  
  const pollTimerRef = useRef(null)
  const wsRef = useRef(null)

  // Load projects on mount
  useEffect(() => {
    loadProjects()
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPolling()
      disconnectSSE()
    }
  }, [])

  // Load all projects
  const loadProjects = async () => {
    try {
      const res = await fetch(`${API_BASE}/projects`)
      const data = await res.json()
      setProjects(data.projects || [])
    } catch (err) {
      console.error('Failed to load projects:', err)
    }
  }

  // Create new project
  const createProject = async (name) => {
    try {
      const res = await fetch(`${API_BASE}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      })
      const data = await res.json()
      await loadProjects()
      return data
    } catch (err) {
      console.error('Failed to create project:', err)
      return null
    }
  }

  // Select project and load sessions
  const selectProject = async (project) => {
    stopPolling()
    setCurrentProject(project)
    setCurrentSession(null)
    setMessages([])
    
    try {
      const res = await fetch(`${API_BASE}/projects/${project.id}/sessions`)
      const data = await res.json()
      setSessions(data.sessions || [])
      setShowProjects(false)
      setShowSessions(true)
    } catch (err) {
      console.error('Failed to load sessions:', err)
      setSessions([])
    }
  }

  // Create new session
  const createSession = async (initialMessage) => {
    if (!currentProject) return

    try {
      const res = await fetch(
        `${API_BASE}/projects/${currentProject.id}/sessions`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ initial_message: initialMessage })
        }
      )
      const data = await res.json()
      
      const newSession = {
        session_id: data.session_id,
        project_id: currentProject.id,
        title: data.title
      }
      
      setCurrentSession(newSession)
      setSessions(prev => [newSession, ...prev])
      setMessages([])
      setShowSessions(false)
      
      return newSession
    } catch (err) {
      console.error('Failed to create session:', err)
      return null
    }
  }

  // Select existing session
  const selectSession = async (session) => {
    stopPolling()
    setCurrentSession(session)
    await loadSessionMessages(session.id || session.session_id)
    setShowSessions(false)
  }

  // Load messages for a session
  const loadSessionMessages = async (sessionId) => {
    if (!currentProject || !sessionId) return
    
    try {
      // Use dedicated /messages endpoint
      const res = await fetch(
        `${API_BASE}/projects/${currentProject.id}/sessions/${sessionId}/messages`
      )
      const data = await res.json()
      setMessages(data.messages || [])
    } catch (err) {
      console.error('Failed to load messages:', err)
      setMessages([])
    }
  }

  // Send message (backend executes automatically)
  const sendMessage = async (content) => {
    const sessionId = currentSession?.id || currentSession?.session_id
    if (!currentSession || !currentProject || !sessionId) {
      console.error('Missing session or project', { currentSession, currentProject, sessionId })
      return
    }
    
    console.log('Sending message via session:', sessionId)
    
    setIsLoading(true)
    
    try {
      // Send message - backend executes automatically in background thread
      const res = await fetch(
        `${API_BASE}/projects/${currentProject.id}/sessions/${sessionId}/messages`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content })
        }
      )
      console.log('Response:', res.status)
      
      // Start polling (with SSE) for response
      startPolling(sessionId)
    } catch (err) {
      console.error('Failed to send message:', err)
      setIsLoading(false)
    }
  }
  
  // Start polling for messages
  const startPolling = (sessionId) => {
    // Also connect to SSE for real-time updates
    connectSSE(sessionId)
    
    let count = 0
    const maxCount = 60
    const interval = 1000
    
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
    }
    
    pollTimerRef.current = setInterval(async () => {
      count++
      
      try {
        // Use dedicated /messages endpoint for polling
        const res = await fetch(
          `${API_BASE}/projects/${currentProject.id}/sessions/${sessionId}/messages`
        )
        const data = await res.json()
        const newMsgs = data.messages || []
        
        // Always update messages from backend (don't compare length)
        if (newMsgs.length > 0) {
          setMessages(newMsgs)
        }
        
        // Check if agent responded (has assistant message)
        const hasAssistant = newMsgs.some(m => m.role === 'assistant')
        
        if (hasAssistant || count >= maxCount) {
          stopPolling()
        }
      } catch (err) {
        console.error('Poll error:', err)
      }
    }, interval)
  }
  
  // Stop polling
  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
    setIsLoading(false)
  }
  
  // Connect to SSE for real-time updates
  const connectSSE = (sessionId) => {
    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }
    
    // Determine the actual session ID
    const actualSessionId = sessionId || currentSession?.id || currentSession?.session_id
    if (!actualSessionId) return
    
    const eventSource = new EventSource(`/sse/${actualSessionId}`)
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log('SSE message:', data)
        
        // Handle different event types
        if (data.role === 'assistant' || data.role === 'user') {
          // It's a message - reload from backend
          loadSessionMessages(actualSessionId)
        }
      } catch (e) {
        console.error('SSE parse error:', e)
      }
    }
    
    eventSource.addEventListener('message', (e) => {
      const data = JSON.parse(e.data)
      console.log('Message event:', data)
      // Reload messages when we get a message event
      loadSessionMessages(actualSessionId)
    })
    
    eventSource.addEventListener('action', (e) => {
      const data = JSON.parse(e.data)
      console.log('Action event:', data)
    })
    
    eventSource.addEventListener('completed', (e) => {
      console.log('Agent completed')
      loadSessionMessages(actualSessionId)
      stopPolling()
    })
    
    eventSource.onerror = (e) => {
      console.log('SSE error:', e)
      eventSource.close()
    }
    
    // Store for cleanup
    wsRef.current = eventSource
  }
  
  // Disconnect SSE
  const disconnectSSE = () => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }

  const goBackToProjects = () => {
    stopPolling()
    setCurrentProject(null)
    setCurrentSession(null)
    setSessions([])
    setMessages([])
    setShowProjects(true)
    setShowSessions(false)
  }

  const goBackToSessions = () => {
    stopPolling()
    disconnectSSE()
    setCurrentSession(null)
    setMessages([])
    setShowSessions(true)
  }

  return (
    <div className="app">
      <Header 
        connected={!isLoading}
        project={currentProject}
        session={currentSession}
        onOpenSettings={() => setShowSettings(true)}
        onGoBack={currentSession ? goBackToSessions : 
                  currentProject ? goBackToProjects : null}
      />
      
      <main className="chat">
        {!currentProject ? (
          <ProjectPanel
            projects={projects}
            onSelectProject={selectProject}
            onCreateProject={createProject}
          />
        ) : currentSession ? (
          <>
            <MessageList messages={messages} isLoading={isLoading} />
            <ChatInput 
              onSend={sendMessage} 
              disabled={isLoading}
            />
          </>
        ) : (
          <SessionList
            sessions={sessions}
            onSelectSession={selectSession}
            onCreateSession={createSession}
          />
        )}
      </main>

      <SettingsModal 
        isOpen={showSettings} 
        onClose={() => setShowSettings(false)} 
      />
    </div>
  )
}

export default App