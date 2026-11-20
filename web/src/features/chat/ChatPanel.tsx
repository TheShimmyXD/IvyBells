// El chat propio del autor (pestana Chat del panel del Agente), como el de Qt: arriba el
// modelo y el esfuerzo del chat (aparte del Agente); en el centro las peticiones y las
// respuestas en Markdown; abajo el cuadro (Enter envia, Mayus+Enter salta de linea), el
// primer texto de la ultima respuesta, Vaciar y Enviar o Cancelar.
import { useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import Dropdown from "../../shared/Dropdown";
import Icon from "../../shared/Icon";
import ChatAnswer from "./ChatAnswer";
import { firstTextLabel, turnSetup, turnStage, type ChatView } from "./chatView";
import type { Chat } from "./useChat";
import "./chat.css";

const PLACEHOLDER =
  "Pídele algo sobre la conversación o el proyecto (Enter envía, Mayús+Enter salta)";
const EMPTY_TEXT =
  "Chat sin perfil: ve el contexto del proyecto y lo que se ha dicho en los dos canales, " +
  "no las respuestas del agente.";
/** Pixeles desde el fondo que aun cuentan como "abajo" para seguir la respuesta. */
const STICK_PX = 24;

function Turns({ view }: { view: ChatView }) {
  if (view.turns.length === 0) {
    return <p className="chat-empty">{EMPTY_TEXT}</p>;
  }
  return view.turns.map((turn, index) => {
    const stage = turnStage(turn);
    return (
      <article key={`${index}-${turn.clock}`} className="chat-turn" data-stage={stage}>
        <p className="chat-turn-head">
          <strong>Tú</strong>
          <span className="chat-clock">{turn.clock}</span>
          <span>{turnSetup(turn, view.choices)}</span>
        </p>
        <blockquote className="chat-request">{turn.request}</blockquote>
        {stage === "waiting" ? (
          <p className="chat-note">Esperando a {turn.model}...</p>
        ) : (
          <ChatAnswer text={turn.answer} />
        )}
        {stage === "cancelled" && <p className="chat-note">(cancelado)</p>}
        {stage === "error" && <p className="chat-error">Error: {turn.error}</p>}
      </article>
    );
  });
}

export default function ChatPanel({ chat }: { chat: Chat }) {
  const { view } = chat;
  const [draft, setDraft] = useState("");
  const log = useRef<HTMLDivElement>(null);
  const stick = useRef(true);

  // Como keep_scroll de Qt: si el autor estaba abajo, la respuesta que llega se sigue.
  useLayoutEffect(() => {
    const element = log.current;
    if (element !== null && stick.current) {
      element.scrollTop = element.scrollHeight;
    }
  }, [view?.turns]);

  const onScroll = () => {
    const element = log.current;
    if (element !== null) {
      const below = element.scrollHeight - element.scrollTop - element.clientHeight;
      stick.current = below <= STICK_PX;
    }
  };

  const submit = () => {
    void chat.send(draft).then((sent) => {
      if (sent) {
        setDraft("");
        stick.current = true;
      }
    });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  const sending = view?.sending ?? false;
  return (
    <div className="chat">
      <div className="chat-setup">
        <Dropdown
          label="Modelo del chat"
          value={view?.model ?? ""}
          options={view?.choices.models ?? []}
          disabled={view === null}
          onChange={chat.setModel}
        />
        <Dropdown
          label="Esfuerzo del chat (aparte del agente)"
          value={view?.effort ?? ""}
          options={view?.choices.efforts ?? []}
          disabled={view === null}
          onChange={chat.setEffort}
        />
      </div>
      <div
        className="chat-log"
        role="log"
        aria-label="Chat con Claude"
        ref={log}
        onScroll={onScroll}
      >
        {view === null ? (
          <p className="chat-empty">Conectando con el chat...</p>
        ) : (
          <Turns view={view} />
        )}
      </div>
      {chat.error !== null && (
        <p className="chat-error" role="alert">
          {chat.error}
        </p>
      )}
      <textarea
        className="chat-input"
        aria-label="Petición para el chat"
        placeholder={PLACEHOLDER}
        rows={3}
        value={draft}
        disabled={view === null}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="chat-actions">
        <span className="chat-first">{firstTextLabel(view?.lastFirstText ?? null)}</span>
        <button
          type="button"
          className="chat-button"
          disabled={view === null || view.turns.length === 0}
          onClick={chat.clear}
        >
          <Icon name="trash" size={14} />
          Vaciar
        </button>
        {sending ? (
          <button type="button" className="chat-button" data-action="cancel" onClick={chat.cancel}>
            <Icon name="stop" size={14} />
            Cancelar
          </button>
        ) : (
          <button
            type="button"
            className="chat-button"
            data-action="send"
            disabled={view === null || draft.trim() === ""}
            onClick={submit}
          >
            <Icon name="paper-plane-tilt" size={14} />
            Enviar
          </button>
        )}
      </div>
    </div>
  );
}
