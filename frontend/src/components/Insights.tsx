import { useEffect, useState } from "react";
import { api } from "../api";
import type { Insight, NLAnswer } from "../types";

export function Insights() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [question, setQuestion] = useState("Why did margins drop last month?");
  const [answer, setAnswer] = useState<NLAnswer | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .insights()
      .then(setInsights)
      .catch(() => setInsights([]))
      .finally(() => setLoading(false));
  }, []);

  const ask = async () => {
    setAnswer(await api.ask(question));
  };

  return (
    <div className="insights">
      <section className="nlq">
        <h3>Ask a question</h3>
        <div className="ask-row">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder="e.g. show revenue by region"
          />
          <button onClick={ask}>Ask</button>
        </div>
        {answer && (
          <div className="answer">
            <p className="answer-text">{answer.answer}</p>
            <p className="answer-meta">
              Resolved to metric <code>{answer.resolved_query.metric}</code> (intent:{" "}
              {answer.resolved_query.intent}). {answer.explanation}
            </p>
          </div>
        )}
      </section>

      <section>
        <h3>Automated insights</h3>
        {loading && <div className="loading">Scanning metrics…</div>}
        {!loading && insights.length === 0 && <div className="empty">No insights yet — run a sync.</div>}
        <div className="insight-list">
          {insights.map((i) => (
            <div key={i.id} className={`insight sev-${i.severity}`}>
              <div className="insight-head">
                <span className={`badge ${i.severity}`}>{i.severity}</span>
                <span className="insight-title">{i.title}</span>
                <span className="insight-kind">{i.kind}</span>
              </div>
              <p className="insight-explain">{i.explanation}</p>
              {i.recommended_actions.length > 0 && (
                <ul className="actions">
                  {i.recommended_actions.map((a, idx) => (
                    <li key={idx}>{a}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
