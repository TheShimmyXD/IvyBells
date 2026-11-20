// La respuesta del Agente para leerla en voz alta: la vigente grande, con la cita de lo
// enviado y como va; debajo las anteriores, la mas nueva primero.
import type { AgentTurn } from "../../api/types";
import Icon from "../../shared/Icon";
import { olderTag, quoteText, turnNote, type AnswerBoard } from "./agentView";

function Quote({ turn }: { turn: AgentTurn }) {
  return (
    <p className="live-quote" title={quoteText(turn.fragment)}>
      <Icon name="quotes" size={12} />
      <span>{quoteText(turn.fragment)}</span>
    </p>
  );
}

function stage(turn: AgentTurn): string {
  if (turn.error !== "") {
    return "error";
  }
  return turn.done || turn.cancelled ? "done" : "writing";
}

export default function AgentAnswer({ card, older }: AnswerBoard) {
  return (
    <div className="live-answers">
      {card !== null && (
        <article className="live-answer" aria-label="Respuesta" data-stage={stage(card)}>
          <Quote turn={card} />
          <p className="live-answer-text">{card.answer}</p>
          {card.error !== "" && <p className="live-answer-error">Error: {card.error}</p>}
          <p className="live-answer-note">{turnNote(card)}</p>
        </article>
      )}
      {older.length > 0 && (
        <section className="live-older" aria-label="Anteriores">
          <h2>Anteriores</h2>
          {older.map((turn) => (
            <article key={`${turn.clock}-${turn.fragment}`} data-tag={olderTag(turn) ?? undefined}>
              <p className="live-older-head">
                <span className="live-clock">{turn.clock}</span>
                <span className="live-older-quote">{quoteText(turn.fragment)}</span>
                {olderTag(turn) !== null && <span className="live-tag">{olderTag(turn)}</span>}
              </p>
              <p className="live-older-text">{turn.answer}</p>
              {turn.error !== "" && <p className="live-answer-error">Error: {turn.error}</p>}
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
