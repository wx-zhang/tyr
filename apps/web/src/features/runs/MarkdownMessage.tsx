import {
  useId,
  useState,
  type ComponentPropsWithoutRef,
  type ReactNode,
} from "react";
import Prism from "prismjs";
import "prismjs/components/prism-diff";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

const LONG_MESSAGE_CHARACTERS = 4_000;

type MarkdownMessageProps = {
  content: string;
};

type ExpandableMarkdownMessageProps = MarkdownMessageProps & {
  previewCharacters?: number;
  expandLabel?: string;
};

function safeUrlTransform(url: string): string {
  if (url.startsWith("#") || /^https?:\/\//i.test(url))
    return defaultUrlTransform(url);
  return "";
}

function SafeLink({ href, children, ...props }: ComponentPropsWithoutRef<"a">) {
  if (!href) return <span>{children}</span>;
  return (
    <a {...props} href={href} rel="noreferrer noopener" target="_blank">
      {children}
    </a>
  );
}

function MessageHeading({ children }: { children?: ReactNode }) {
  return <h4>{children}</h4>;
}

function HighlightedCode({
  className,
  children,
  ...props
}: ComponentPropsWithoutRef<"code">) {
  const language = /language-([\w-]+)/.exec(className ?? "")?.[1];
  const grammar = language ? Prism.languages[language] : undefined;
  if (!language || !grammar) {
    return (
      <code {...props} className={className}>
        {children}
      </code>
    );
  }
  const source = String(children).replace(/\n$/, "");
  const highlighted = Prism.highlight(source, grammar, language);
  return (
    <code
      {...props}
      className={className}
      dangerouslySetInnerHTML={{ __html: highlighted }}
    />
  );
}

function RenderedMarkdown({ content }: MarkdownMessageProps) {
  return (
    <div className="markdown-message">
      <ReactMarkdown
        skipHtml
        remarkPlugins={[remarkGfm]}
        urlTransform={safeUrlTransform}
        components={{
          a: SafeLink,
          h1: MessageHeading,
          h2: MessageHeading,
          h3: MessageHeading,
          h4: MessageHeading,
          h5: MessageHeading,
          h6: MessageHeading,
          code: HighlightedCode,
          img: ({ alt }) => <span>{alt ?? "Image omitted"}</span>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export function MarkdownMessage({ content }: MarkdownMessageProps) {
  if (content.length <= LONG_MESSAGE_CHARACTERS) {
    return <RenderedMarkdown content={content} />;
  }
  return (
    <details className="long-message">
      <summary>Show full message</summary>
      <RenderedMarkdown content={content} />
    </details>
  );
}

export function ExpandableMarkdownMessage({
  content,
  previewCharacters = 360,
  expandLabel = "Show full justification",
}: ExpandableMarkdownMessageProps) {
  const [expanded, setExpanded] = useState(false);
  const contentId = useId();
  if (content.length <= previewCharacters) {
    return <RenderedMarkdown content={content} />;
  }
  return (
    <div className="expandable-message">
      {expanded ? (
        <div id={contentId} className="long-message-content">
          <RenderedMarkdown content={content} />
        </div>
      ) : (
        <RenderedMarkdown
          content={`${content.slice(0, previewCharacters).trimEnd()}…`}
        />
      )}
      <button
        type="button"
        className="long-message-toggle"
        aria-expanded={expanded}
        aria-controls={contentId}
        onClick={() => setExpanded((current) => !current)}
      >
        {expanded ? "Hide full justification" : expandLabel}
      </button>
    </div>
  );
}
