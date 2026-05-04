import { useState, useRef, useEffect } from 'react'
import Header from './components/Header'
import MessageList from './components/MessageList'
import ChatInput from './components/ChatInput'
import Welcome from './components/Welcome'
import SettingsModal from './components/SettingsModal'
import ProjectPanel from './components/ProjectPanel'
import SessionList from './components/SessionList'

const API_BASE = '/api'

function App() {
  // State
  const [currentProject, setCurrentProject] = useState(null)
  const [projects, setProjects] = useState([])
  const [currentSession, setCurrentSession] = useState(null)
  const [sessions, setSessions] = useState([])
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [connected, setConnected] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showProjects, setShowProjects] = useState(true)
  const [showSessions, setShowSessions] = useState(false)
  const wsRef = useRef(null)

  // Load projects on mount
  useEffect(() => {
    loadProjects()
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  // Connect WebSocket when session is created
  useEffect(() => {
    if (currentSession) {
      connectWebSocket(currentSession.session_id)
    }
  }, [currentSession])

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
    setCurrentProject(project)
    setCurrentSession(null)
    setMessages([])
    
    // Load sessions for this project
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

  // Create new session (conversation) in current project
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
  const selectSession = (session) => {
    setCurrentSession(session)
    // Load session messages
    loadSessionMessages(session.session_id)
    setShowSessions(false)
  }

  // Load messages for a session
  const loadSessionMessages = async (sessionId) => {
    if (!currentProject) return
    
    try {
      const res = await fetch(
        `${API_BASE}/projects/${currentProject.id}/sessions/${sessionId}`
      )
      const data = await res.json()
      setMessages(data.messages || [])
    } catch (err) {
      console.error('Failed to load messages:', err)
      setMessages([])
    }
  }

  // Connect WebSocket
  const connectWebSocket = (sessionId) => {
    if (wsRef.current) {
      wsRef.current.close()
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(
      `${protocol}//${window.location.host}/ws/${sessionId}`
    )
    
    ws.onopen = () => {
      setConnected(true)
    }
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleWebSocketMessage(data)
      } catch (e) {
        // Handle non-JSON messages (plain text)
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: event.data,
          timestamp: new Date().toISOString()
        }])
      }
    }
    
    ws.onclose = () => {
      setConnected(false)
    }
    
    ws.onerror = (err) => {
      console.error('WebSocket error:', err)
    }
    
    wsRef.current = ws
  }

  const handleWebSocketMessage = (data) => {
    // Handle different message types
    if (data.type === 'status') {
      setIsLoading(data.status === 'running')
      return
    }
    
    if (data.event_type === 'agent_thought' || data.event_type === 'agent_action') {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.content || data.action,
        metadata: data,
        timestamp: new Date().toISOString()
      }])
      return
    }
    
    if (data.type === 'complete' || data.type === 'done') {
      setIsLoading(false)
      return
    }
    
    if (data.type === 'error') {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${data.error}`,
        timestamp: new Date().toISOString()
      }])
      setIsLoading(false)
      return
    }

    // Default: treat as assistant message
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: typeof data === 'string' ? data : JSON.stringify(data),
      timestamp: new Date().toISOString()
    }])
  }

  const sendMessage = async (content) => {
    // Add user message immediately
    setMessages(prev => [...prev, {
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    }])

    // Save message to session
    if (currentSession && currentProject) {
      try {
        await fetch(
          `${API_BASE}/projects/${currentProject.id}/sessions/${currentSession.session_id}/messages`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: content })
          }
        )
      } catch (err) {
        console.error('Failed to save message:', err)
      }
    }

    // Send via WebSocket if connected
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'message',
        content
      }))
      setIsLoading(true)
    } else if (currentSession && currentProject) {
      // Fallback: start the agent
      try {
        await fetch(
          `${API_BASE}/projects/${currentProject.id}/sessions/${currentSession.session_id}/run`,
          { method: 'POST' }
        )
        setIsLoading(true)
      } catch (err) {
        console.error('Failed to run session:', err)
      }
    }
  }

  const goBackToProjects = () => {
    setCurrentProject(null)
    setCurrentSession(null)
    setSessions([])
    setMessages([])
    setShowProjects(true)
    setShowSessions(false)
  }

  const goBackToSessions = () => {
    setCurrentSession(null)
    setMessages([])
    setShowSessions(true)
  }

  // Render
  return (
    <div className="app">
      <Header 
        connected={connected}
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
              disabled={isLoading || !connected}
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