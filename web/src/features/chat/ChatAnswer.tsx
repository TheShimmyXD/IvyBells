// La respuesta de Claude en Markdown (como el chat de Qt). Sin HTML del texto ni imagenes:
// una imagen cargaria una URL de afuera. Los enlaces abren aparte, nunca sobre la ventana.
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const PLUGINS = [remarkGfm];
const BLOCKED = ["img"];

const COMPONENTS: Components = {
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer noopener" title={href}>
      {children}
    </a>
  ),
};

export default function ChatAnswer({ text }: { text: string }) {
  return (
    <div className="chat-answer">
      <Markdown
        remarkPlugins={PLUGINS}
        disallowedElements={BLOCKED}
        unwrapDisallowed
        components={COMPONENTS}
      >
        {text}
      </Markdown>
    </div>
  );
}
