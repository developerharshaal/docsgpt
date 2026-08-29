import { useState, type SubmitEvent } from 'react'
import './App.css'

type Source = {
  n: number
  url: string
  title: string
}

type AnswerResponse = {
  answer: string
  sources: Source[]
  route: 'greeting' | 'rag' | 'agent'
}

const API_URL = 'http://localhost:8000/ask-smart'

function App() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<AnswerResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      const data = await response.json()
      setAnswer(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>DocsGPT</h1>
        <p>Ask a question about the FastAPI documentation.</p>
      </header>

      <form className="ask-form" onSubmit={handleSubmit}>
        <input
          className="ask-input"
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="How do I define a path parameter?"
        />
        <button className="ask-button" type="submit" disabled={loading}>
          {loading ? 'Asking...' : 'Ask'}
        </button>
      </form>

      {error && (
        <div className='error-text'>
          <span className='error-message'>{error}</span>
        </div>
      )

      }
      {answer && (
        <div className="answer-card">
          <span className="answer-route">{answer.route}</span>
          <p className="answer-text">{answer.answer}</p>

          {answer.sources.map((item) => (
            <a className='source-tag' href={item.url} key={item.n}>{item.title}</a>
          ))}
        </div>
      )}
    </div>
  )
}

export default App
