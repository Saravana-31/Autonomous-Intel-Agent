import React, { useState, useEffect } from 'react';
import './App.css';

const API_BASE = 'http://localhost:8000';

function App() {
  const [companies, setCompanies] = useState([]);
  const [selectedCompany, setSelectedCompany] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [serverStatus, setServerStatus] = useState('checking');

  useEffect(() => {
    checkServer();
    fetchCompanies();
  }, []);

  const checkServer = async () => {
    try {
      const res = await fetch(`${API_BASE}/`);
      const data = await res.json();
      // Check if both LLMs are available
      const isPrimaryAvailable = data.llm?.primary?.available;
      setServerStatus(isPrimaryAvailable ? 'ready' : 'loading');
    } catch {
      setServerStatus('offline');
    }
  };

  const fetchCompanies = async () => {
    try {
      const res = await fetch(`${API_BASE}/companies`);
      const data = await res.json();
      setCompanies(data.companies || []);
      if (data.companies?.length > 0) {
        setSelectedCompany(data.companies[0]);
      }
    } catch {
      setCompanies([]);
    }
  };

  const processCompany = async () => {
    if (!selectedCompany) return;
    
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}/process/${selectedCompany}`);
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Processing failed');
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <div className="background-pattern"></div>
      
      <header className="header">
        <div className="logo">
          <span className="logo-icon">◈</span>
          <h1>Company Intelligence Agent</h1>
        </div>
        <div className={`status status-${serverStatus}`}>
          <span className="status-dot"></span>
          {serverStatus === 'ready' && 'LLM Ready'}
          {serverStatus === 'loading' && 'LLM Loading...'}
          {serverStatus === 'offline' && 'Server Offline'}
          {serverStatus === 'checking' && 'Checking...'}
        </div>
      </header>

      <main className="main">
        <section className="control-panel">
          <div className="input-group">
            <label>Select Company</label>
            <select 
              value={selectedCompany} 
              onChange={(e) => setSelectedCompany(e.target.value)}
              disabled={loading || companies.length === 0}
            >
              {companies.length === 0 && <option>No companies found</option>}
              {companies.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          
          <button 
            className="process-btn"
            onClick={processCompany}
            disabled={loading || !selectedCompany || serverStatus !== 'ready'}
          >
            {loading ? (
              <>
                <span className="spinner"></span>
                Processing...
              </>
            ) : (
              <>
                <span className="btn-icon">⚡</span>
                Extract Intelligence
              </>
            )}
          </button>

          {error && (
            <div className="error-box">
              <span className="error-icon">✕</span>
              {error}
            </div>
          )}
        </section>

        {result && (
          <div className="results">
            <section className="result-card company-card">
              <div className="card-header">
                <h2>{result.profile.company_name || 'Unknown Company'}</h2>
                {result.profile.industry && (
                  <span className="industry-tag">{result.profile.industry}</span>
                )}
              </div>
              
              {result.profile.description_short && (
                <p className="description">{result.profile.description_short}</p>
              )}
            </section>

            <div className="results-grid">
              {result.profile.products_services?.length > 0 && (
                <section className="result-card">
                  <h3>
                    <span className="card-icon">◆</span>
                    Products & Services
                  </h3>
                  <ul className="tag-list">
                    {result.profile.products_services.map((item, i) => (
                      <li key={i} className="tag tag-product">{item}</li>
                    ))}
                  </ul>
                </section>
              )}

              {result.profile.locations?.length > 0 && (
                <section className="result-card">
                  <h3>
                    <span className="card-icon">◇</span>
                    Locations
                  </h3>
                  <ul className="tag-list">
                    {result.profile.locations.map((loc, i) => {
                      // Handle both string (legacy) and object (new Location schema)
                      if (typeof loc === 'string') {
                        return <li key={i} className="tag tag-location">{loc}</li>;
                      } else if (loc && typeof loc === 'object') {
                        return (
                          <li key={i} className="tag tag-location">
                            <span className="location-type">{loc.type}</span>
                            {loc.city && loc.country ? `${loc.city}, ${loc.country}` : loc.address}
                          </li>
                        );
                      }
                      return null;
                    })}
                  </ul>
                </section>
              )}

              {result.profile.tech_stack?.length > 0 && (
                <section className="result-card">
                  <h3>
                    <span className="card-icon">◈</span>
                    Tech Stack
                  </h3>
                  <ul className="tag-list">
                    {result.profile.tech_stack.map((tech, i) => (
                      <li key={i} className="tag tag-tech">{tech}</li>
                    ))}
                  </ul>
                </section>
              )}

              {(result.profile.contact?.email || result.profile.contact?.phone) && (
                <section className="result-card">
                  <h3>
                    <span className="card-icon">▣</span>
                    Contact
                  </h3>
                  <div className="contact-info">
                    {result.profile.contact.email && (
                      <p><span className="label">Email:</span> {result.profile.contact.email}</p>
                    )}
                    {result.profile.contact.phone && (
                      <p><span className="label">Phone:</span> {result.profile.contact.phone}</p>
                    )}
                  </div>
                </section>
              )}
            </div>

            {result.profile.key_people?.length > 0 && (
              <section className="result-card people-card">
                <h3>
                  <span className="card-icon">◉</span>
                  Key People
                </h3>
                <div className="people-grid">
                  {result.profile.key_people.map((person, i) => (
                    <div key={i} className="person-card">
                      <div className="person-avatar">
                        {person.name?.charAt(0) || '?'}
                      </div>
                      <div className="person-info">
                        <h4>{person.name}</h4>
                        <p className="person-title">{person.title}</p>
                        {person.role_category && (
                          <span className="role-tag">{person.role_category}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section className="result-card graph-card">
              <h3>
                <span className="card-icon">⬡</span>
                Knowledge Graph
              </h3>
              <div className="graph-stats">
                <div className="stat">
                  <span className="stat-value">{result.graph.nodes?.length || 0}</span>
                  <span className="stat-label">Nodes</span>
                </div>
                <div className="stat">
                  <span className="stat-value">{result.graph.edges?.length || 0}</span>
                  <span className="stat-label">Edges</span>
                </div>
              </div>
              
              <div className="graph-data">
                <details>
                  <summary>View Raw Graph JSON</summary>
                  <pre>{JSON.stringify(result.graph, null, 2)}</pre>
                </details>
              </div>
            </section>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Offline Company Intelligence Agent • Powered by Local LLM</p>
      </footer>
    </div>
  );
}

export default App;
