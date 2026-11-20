// La conversacion en burbujas: Ellos a la izquierda y Tu a la derecha, intercaladas por
// hora; lo provisional en gris y cursiva al final; Reanudada en su sitio. Baja sola
// mientras se sigue en vivo; si se sube a leer, aparece Seguir en vivo.
import { useLayoutEffect, useRef, useState } from "react";
import type { SourceId } from "../../api/types";
import Icon from "../../shared/Icon";
import type { IconName } from "../../shared/phosphor";
import type { MarkButton } from "./agentMarks";
import type { PhraseMark } from "./agentView";
import type { Bubble } from "./conversation";

/** Lo que el Agente necesita de la conversacion: a quien escucha y como va cada frase. */
export interface ConversationAgent {
  speaker: SourceId;
  marks: Map<number, PhraseMark>;
  onMark: (bubble: Bubble, button: MarkButton) => void;
}

interface ConversationProps {
  bubbles: Bubble[];
  closed: SourceId[];
  agent?: ConversationAgent;
}

const MARK_ICONS: Record<PhraseMark, [IconName, string]> = {
  start: ["flag", "Inicio marcado"],
  flight: ["circle-notch", "Enviando"],
  sent: ["paper-plane-tilt", "Enviada"],
};

// Distancia al fondo (px) que todavia cuenta como estar siguiendo en vivo.
const FOLLOW_SLACK_PX = 40;

export default function Conversation({ bubbles, closed, agent }: ConversationProps) {
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
            <Phrase key={bubble.key} bubble={bubble} closed={closed} agent={agent} />
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

interface PhraseProps {
  bubble: Extract<Bubble, { kind: "phrase" }>;
  closed: SourceId[];
  agent?: ConversationAgent;
}

/** Una frase; las finales del interlocutor se marcan con clic izquierdo y derecho. */
function Phrase({ bubble, closed, agent }: PhraseProps) {
  const markable = agent !== undefined && bubble.source === agent.speaker && bubble.index !== null;
  const mark = markable && bubble.index !== null ? agent.marks.get(bubble.index) : undefined;
  const click = (button: MarkButton) => agent?.onMark(bubble, button);
  return (
    <li
      className="live-phrase"
      data-source={bubble.source}
      data-final={bubble.final}
      data-closed={closed.includes(bubble.source)}
      data-markable={markable}
      data-mark={mark}
      aria-label={bubble.source === "ellos" ? "Ellos" : "Tú"}
      onClick={markable ? () => click("left") : undefined}
      onContextMenu={
        markable
          ? (event) => {
              event.preventDefault();
              click("right");
            }
          : undefined
      }
    >
      <span className="live-bubble">{bubble.final ? bubble.text : `${bubble.text} …`}</span>
      <span className="live-clock">
        {bubble.clock}
        {mark !== undefined && (
          <span className="live-mark" title={MARK_ICONS[mark][1]}>
            <Icon name={MARK_ICONS[mark][0]} size={11} />
          </span>
        )}
      </span>
    </li>
  );
}
