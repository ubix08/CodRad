import { useState, useEffect } from 'react'
import Header from './components/Header'
import MessageList from './components/MessageList'
import ChatInput from './components/ChatInput'
import Welcome from './components/Welcome'
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
  const [pollTimer, setPollTimer] = useState(null)

  // Load projects on mount
  useEffect(() => {
    loadProjects()
    return () => {
      if (pollTimer) clearInterval(pollTimer)
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
    setCurrentProject(project)
    setCurrentSession(null)
    setMessages([])
    stopPolling()
    
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
    setCurrentSession(session)
    stopPolling()
    await loadSessionMessages(session.id || session.session_id)
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

  // Send message and run agent with polling
  const sendMessage = async (content) => {
    const sessionId = currentSession?.id || currentSession?.session_id
    if (!currentSession || !currentProject || !sessionId) return
    
    // Add user message to UI immediately
    setMessages(prev => [...prev, {
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    }])
    
    setIsLoading(true)
    
    try {
      // 1. Save message to session
      await fetch(
        `${API_BASE}/projects/${currentProject.id}/sessions/${sessionId}/messages`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content })
        }
      )
      
      // 2. Start the agent
      await fetch(
        `${API_BASE}/projects/${currentProject.id}/sessions/${sessionId}/run`,
        { method: 'POST' }
      )
      
      // 3. Poll for response
      startPolling(sessionId)
    } catch (err) {
      console.error('Failed to run session:', err)
      setIsLoading(false)
    }
  }
  
  // Start polling for messages
  const startPolling = (sessionId) => {
    let attempts = 0
    const maxAttempts = 30
    
    const timer = setInterval(async () => {
      attempts++
      
      try {
        const res = await fetch(
          `${API_BASE}/projects/${currentProject.id}/sessions/${sessionId}`
        )
        const data = await res.json()
        const newMessages = data.messages || []
        
        // Check if there are new messages or assistant response
        if (newMessages.length > messages.length) {
          setMessages(newMessages)
        }
        
        // Check for assistant message to know we're done
        const hasAssistant = newMessages.some(m => m.role === 'assistant')
        
        if (hasAssistant || attempts >= maxAttempts) {
          clearInterval(timer)
          setPollTimer(null)
          setIsLoading(false)
        }
      } catch (err) {
        console.error('Polling error:', err)
      }
    }, 1000)
    
    setPollTimer(timer)
  }
  
  // Stop polling
  const stopPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer)
      setPollTimer(null)
    }
    setIsLoading(false)
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