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

  // Load projects on mount
  useEffect(() => {
    loadProjects()
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPolling()
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

  // Send message and run agent
  const sendMessage = async (content) => {
    const sessionId = currentSession?.id || currentSession?.session_id
    if (!currentSession || !currentProject || !sessionId) {
      console.error('Missing session or project', { currentSession, currentProject, sessionId })
      return
    }
    
    console.log('Sending message via session:', sessionId)
    
    setIsLoading(true)
    
    try {
      // 1. Save message to session
      const saveRes = await fetch(
        `${API_BASE}/projects/${currentProject.id}/sessions/${sessionId}/messages`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content })
        }
      )
      console.log('Save message response:', saveRes.status)
      
      // 2. Run the agent
      const runRes = await fetch(
        `${API_BASE}/projects/${currentProject.id}/sessions/${sessionId}/run`,
        { method: 'POST' }
      )
      console.log('Run response:', runRes.status)
      
      const runData = await runRes.json()
      console.log('Run data:', runData)
      
      // 3. Immediately load fresh messages from backend
      await loadSessionMessages(sessionId)
      
      // 4. Start polling for response
      startPolling(sessionId)
    } catch (err) {
      console.error('Failed to run session:', err)
      setIsLoading(false)
    }
  }
  
  // Start polling for messages
  const startPolling = (sessionId) => {
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