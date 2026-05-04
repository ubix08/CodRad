import { useState } from 'react'

function SessionList({ sessions, onSelectSession, onCreateSession }) {
  const [initialMessage, setInitialMessage] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!initialMessage.trim()) return
    
    setIsCreating(true)
    await onCreateSession(initialMessage.trim())
    setInitialMessage('')
    setIsCreating(false)
  }

  return (
    <div className="session-list">
      <div className="panel-header">
        <h2>Conversations</h2>
        <p>Select a session or start a new conversation</p>
      </div>

      {/* New conversation form */}
      <form className="create-form" onSubmit={handleCreate}>
        <input
          type="text"
          placeholder="What would you like to work on?"
          value={initialMessage}
          onChange={(e) => setInitialMessage(e.target.value)}
          disabled={isCreating}
        />
        <button type="submit" disabled={isCreating || !initialMessage.trim()}>
          {isCreating ? 'Starting...' : 'Start'}
        </button>
      </form>

      {/* Sessions list */}
      <div className="sessions-list">
        {sessions.length === 0 ? (
          <div className="empty-state">
            <p>No conversations yet</p>
            <p className="hint">Start your first conversation above</p>
          </div>
        ) : (
          sessions.map(session => (
            <div
              key={session.id}
              className="session-card"
              onClick={() => onSelectSession(session)}
            >
              <div className="session-icon">💬</div>
              <div className="session-info">
                <h3>{session.title || session.id}</h3>
                <p>
                  {session.created_at 
                    ? new Date(session.created_at).toLocaleString()
                    : 'Just now'}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default SessionList