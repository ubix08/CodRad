import { useState } from 'react'

function ProjectPanel({ projects, onSelectProject, onCreateProject }) {
  const [newProjectName, setNewProjectName] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!newProjectName.trim()) return
    
    setIsCreating(true)
    await onCreateProject(newProjectName.trim())
    setNewProjectName('')
    setIsCreating(false)
  }

  return (
    <div className="project-panel">
      <div className="panel-header">
        <h2>Your Projects</h2>
        <p>Select a project to start working</p>
      </div>

      {/* Create new project form */}
      <form className="create-form" onSubmit={handleCreate}>
        <input
          type="text"
          placeholder="New project name..."
          value={newProjectName}
          onChange={(e) => setNewProjectName(e.target.value)}
          disabled={isCreating}
        />
        <button type="submit" disabled={isCreating || !newProjectName.trim()}>
          {isCreating ? 'Creating...' : 'Create'}
        </button>
      </form>

      {/* Projects list */}
      <div className="projects-grid">
        {projects.length === 0 ? (
          <div className="empty-state">
            <p>No projects yet</p>
            <p className="hint">Create your first project above</p>
          </div>
        ) : (
          projects.map(project => (
            <div
              key={project.id}
              className="project-card"
              onClick={() => onSelectProject(project)}
            >
              <div className="project-icon">
                {project.name.charAt(0).toUpperCase()}
              </div>
              <div className="project-info">
                <h3>{project.name}</h3>
                <p>{project.sessions_count || 0} sessions</p>
              </div>
              {project.has_agents && (
                <span className="badge">Custom Agent</span>
              )}
            </div>
          ))
        )}
      </div>

      {/* Import from GitHub */}
      <div className="import-section">
        <p>Or import from GitHub:</p>
        <button
          className="secondary"
          onClick={() => {
            const url = prompt('Enter GitHub repository URL:')
            if (url) {
              // This will be handled by GitHubPanel
              window.dispatchEvent(new CustomEvent('openGitHubImport', { detail: url }))
            }
          }}
        >
          Import GitHub Repo
        </button>
      </div>
    </div>
  )
}

export default ProjectPanel