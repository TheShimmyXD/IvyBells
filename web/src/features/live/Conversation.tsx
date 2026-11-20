// La conversacion en burbujas: Ellos a la izquierda y Tu a la derecha, intercaladas por
// hora; lo provisional en gris y cursiva al final; Reanudada en su sitio. Baja sola
// mientras se sigue en vivo; si se sube a leer, aparece Seguir en vivo.
import { useLayoutEffect, useRef, useState } from "react";
import type { SourceId } from "../../api/types";
import Icon from "../../shared/Icon";
import type { Bubble } from "./conversation";

interface ConversationProps {
  bubbles: Bubble[];
  closed: SourceId[];
}

// Distancia al fondo (px) que todavia cuenta como estar siguiendo en vivo.
const FOLLOW_SLACK_PX = 40;

export default function Conversation({ bubbles, closed }: ConversationProps) {
  const list = useRef<HTMLOListElement>(null);
  const [following, setFollowing] = useState(true);

  useLayoutEffect(() => {
    const element = list.current;
    if (following && element !== null) {
      element.scrollTop = element.scrollHeight;
    }
  }, [bubbles, following]);

  const onScroll = () => {
    const element = list.current;
    if (element !== null) {
      const gap = element.scrollHeight - element.scrollTop - element.clientHeight;
      setFollowing(gap <= FOLLOW_SLACK_PX);
    }
  };

  return (
    <div className="live-conversation">
      <ol ref={list} className="live-bubbles" aria-label="Conversación" onScroll={onScroll}>
        {bubbles.length === 0 && <li className="live-empty">Todavía no hay frases.</li>}
        {bubbles.map((bubble) =>
          bubble.kind === "resumed" ? (
            <li key={bubble.key} className="live-resumed">
              Reanudada {bubble.clock}
            </li>
          ) : (
            <li
              key={bubble.key}
              className="live-phrase"
              data-source={bubble.source}
              data-final={bubble.final}
              data-closed={closed.includes(bubble.source)}
              aria-label={bubble.source === "ellos" ? "Ellos" : "Tú"}
            >
              <span className="live-bubble">{bubble.final ? bubble.text : `${bubble.text} …`}</span>
              <span className="live-clock">{bubble.clock}</span>
            </li>
          ),
        )}
      </ol>
      {!following && (
        <button
          type="button"
          className="live-follow"
          title="Seguir en vivo"
          onClick={() => setFollowing(true)}
        >
          <Icon name="arrow-down" size={16} />
          <span className="live-follow-text">Seguir en vivo</span>
        </button>
      )}
    </div>
  );
}
