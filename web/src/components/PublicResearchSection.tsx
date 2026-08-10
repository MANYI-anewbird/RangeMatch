import type { DiligenceSearchResult } from "../api/client";

function withoutInlineLinks(text: string) {
  return text
    .replace(/\[([^\]]+)\]\(https?:\/\/[^)]+\)/g, "$1")
    .replace(/\*\*/g, "")
    .replace(/^\s*-\s*/gm, "")
    .trim();
}

function guidanceItems(text: string) {
  const clean = withoutInlineLinks(text);
  const chunks = clean.split(/(?=(?:CURRENT_DROUGHT|LOCAL_AG_GUIDANCE|PUBLIC_LAND_CONSTRAINTS|REGULATION_AND_PERMITS):)/g);
  return chunks
    .map((chunk) => {
      const match = chunk.trim().match(/^(CURRENT_DROUGHT|LOCAL_AG_GUIDANCE|PUBLIC_LAND_CONSTRAINTS|REGULATION_AND_PERMITS):\s*([\s\S]+)$/);
      if (!match) return null;
      const parts = match[2].split(/\s+(?:Follow up|Buyer action):\s*/i);
      return { topic: match[1].replaceAll("_", " ").toLowerCase(), finding: parts[0].trim(), action: parts.slice(1).join(" ").trim() };
    })
    .filter((item): item is { topic: string; finding: string; action: string } => Boolean(item));
}

export function PublicResearchSection({ result }: { result: DiligenceSearchResult | null }) {
  const ready = result?.status === "COMPLETE" && result.sources.length > 0;
  const items = ready ? guidanceItems(result.summary) : [];
  return (
    <section
      className="section-block report-section report-section-research"
      id="research"
      aria-labelledby="research-title"
      data-testid="public-research"
    >
      <div className="report-section-heading">
        <div><span className="report-section-index">06</span><h2 id="research-title">Current rules & local guidance</h2></div>
      </div>
      {ready ? (
        <>
          {result.location_scope && <p className="research-location">Search area: <strong>{result.location_scope}</strong></p>}
          {items.length > 0 ? (
            <div className="research-guidance-grid">
              {items.map((item) => (
                <article className="research-guidance-card" key={item.topic}>
                  <span>{item.topic}</span>
                  <p>{item.finding}</p>
                  {item.action && <p><strong>What to do:</strong> {item.action}</p>}
                </article>
              ))}
            </div>
          ) : <p className="lede">{withoutInlineLinks(result.summary)}</p>}
          <p className="muted">This public-source scan supports due diligence only. It does not change land facts or operation-fit decisions.</p>
          <div className="research-source-grid">
            {result.sources.slice(0, 8).map((source) => (
              <a key={source.source_id} className="research-source-card" href={source.url} target="_blank" rel="noreferrer">
                <strong>{source.title}</strong>
                {(source.publisher || source.domain) &&
                  (source.publisher || source.domain) !== source.title && (
                    <span>{source.publisher || source.domain}</span>
                  )}
              </a>
            ))}
          </div>
        </>
      ) : (
        <div className="research-unavailable" role="note">
          <strong>Current public-source search was not available.</strong>
          <p>The land analysis remains valid; rules and permit questions should be checked directly with the relevant agencies.</p>
        </div>
      )}
    </section>
  );
}
