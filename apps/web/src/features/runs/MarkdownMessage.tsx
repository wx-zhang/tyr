import type { ComponentPropsWithoutRef, ReactNode } from "react";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

const LONG_MESSAGE_CHARACTERS = 4_000;

type MarkdownMessageProps = {
  content: string;
};

function safeUrlTransform(url: string): string {
  if (url.startsWith("#") || /^https?:\/\//i.test(url)) return defaultUrlTransform(url);
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
