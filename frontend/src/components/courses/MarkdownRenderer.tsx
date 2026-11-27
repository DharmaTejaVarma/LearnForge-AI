import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { Copy, Check, Terminal, ChevronDown, ChevronUp, GitBranch, ArrowRight } from 'lucide-react';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

const slugifyHeading = (children: React.ReactNode): string => {
  const extract = (node: any): string => {
    if (typeof node === 'string' || typeof node === 'number') return String(node);
    if (Array.isArray(node)) return node.map(extract).join('');
    if (node?.props?.children) return extract(node.props.children);
    return '';
  };
  return extract(children)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
};

const MermaidDiagramBlock: React.FC<{ definition: string }> = ({ definition }) => {
  const [showRaw, setShowRaw] = useState(false);

  const edges: Array<{ from: string; to: string }> = [];
  const labelMap: Record<string, string> = {};

  definition.split('\n').forEach((line) => {
    const clean = line.trim();
    if (!clean || clean.startsWith('flowchart') || clean.startsWith('graph')) return;
    const nodeMatches = [...clean.matchAll(/([A-Za-z0-9_]+)\s*[\[\(\{]+"?([^\]\)\}"]+)"?[\]\)\}]+/g)];
    nodeMatches.forEach((m) => {
      labelMap[m[1]] = m[2].trim();
    });

    const arrowMatch = clean.match(/([A-Za-z0-9_]+)(?:\[[^\]]*\])?\s*(?:-->|==>|-.->|->)\s*(?:\|[^|]*\|\s*)?([A-Za-z0-9_]+)/);
    if (arrowMatch) {
      const fromId = arrowMatch[1];
      const toId = arrowMatch[2];
      edges.push({
        from: labelMap[fromId] || fromId,
        to: labelMap[toId] || toId,
      });
    }
  });

  const flowChain: string[] = [];
  edges.forEach((e) => {
    if (!flowChain.includes(e.from)) flowChain.push(e.from);
    if (!flowChain.includes(e.to)) flowChain.push(e.to);
  });

  return (
    <div className="my-5 rounded-[12px] border border-brand-soft-border bg-subtle p-4 space-y-3 shadow-sm not-prose">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2 text-brand font-semibold">
          <GitBranch className="h-4 w-4 text-accent" />
          <span>Concept Flow Diagram</span>
        </div>
        <button
          type="button"
          onClick={() => setShowRaw((p) => !p)}
          className="text-[11px] text-ink-secondary hover:text-ink-primary underline underline-offset-2"
        >
          {showRaw ? 'Visual View' : 'View Source'}
        </button>
      </div>

      {showRaw || flowChain.length === 0 ? (
        <pre className="p-3 rounded-[10px] bg-codeblock-bg border border-codeblock-border text-xs font-mono text-codeblock-text overflow-x-auto">
          <code>{definition}</code>
        </pre>
      ) : (
        <div className="flex flex-wrap items-center gap-2.5 py-2">
          {flowChain.map((step, i) => (
            <React.Fragment key={i}>
              <div className="px-3.5 py-2 rounded-[10px] bg-surface border border-brand-soft-border text-xs font-semibold text-ink-primary shadow-sm">
                {step}
              </div>
              {i < flowChain.length - 1 && (
                <ArrowRight className="h-4 w-4 text-accent shrink-0" />
              )}
            </React.Fragment>
          ))}
        </div>
      )}
    </div>
  );
};

const CodeBlock: React.FC<{ language?: string; children: React.ReactNode }> = ({
  language,
  children,
}) => {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const codeString = String(children).replace(/\n$/, '');

  if (language?.toLowerCase() === 'mermaid') {
    return <MermaidDiagramBlock definition={codeString} />;
  }

  const lines = codeString.split('\n');
  const isLong = lines.length > 16;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(codeString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  const displayLang = language ? language.replace(/^language-/, '').toUpperCase() : 'CODE';

  return (
    <div className="my-5 rounded-[12px] border border-codeblock-border bg-codeblock-bg shadow-card overflow-hidden group not-prose">
      <div className="flex items-center justify-between px-4 py-2 bg-codeblock-header border-b border-codeblock-border text-xs">
        <div className="flex items-center gap-2 text-codeblock-muted font-mono">
          <Terminal className="h-3.5 w-3.5 text-indigo-400" />
          <span className="font-semibold text-codeblock-text">{displayLang}</span>
          <span className="text-[10px] opacity-80">({lines.length} lines)</span>
        </div>
        <div className="flex items-center gap-2">
          {isLong && (
            <button
              type="button"
              onClick={() => setExpanded((p) => !p)}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-white/10 hover:bg-white/20 text-codeblock-text text-[11px] transition-colors"
            >
              {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              <span>{expanded ? 'Collapse' : 'Expand'}</span>
            </button>
          )}
          <button
            onClick={handleCopy}
            type="button"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/10 hover:bg-white/20 text-codeblock-text transition-colors text-[11px] font-medium border border-white/15"
            title="Copy code to clipboard"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-emerald-400 font-semibold">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="p-4 overflow-x-auto text-xs md:text-sm leading-relaxed font-mono text-codeblock-text">
          <table className="w-full border-collapse">
            <tbody>
              {lines.map((line, i) => (
                <tr key={i} className="hover:bg-white/5">
                  <td className="pr-4 select-none text-right text-[11px] text-codeblock-muted w-8 align-top">
                    {i + 1}
                  </td>
                  <td className="whitespace-pre text-codeblock-text">{line || ' '}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = '' }) => {
  if (!content) {
    return <p className="text-ink-secondary italic">No content available.</p>;
  }

  return (
    <div className={`prose dark:prose-invert max-w-none text-ink-primary ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-2xl md:text-[28px] font-bold text-ink-primary tracking-tight mt-6 mb-4 border-b border-line pb-3 flex items-center gap-2">
              {children}
            </h1>
          ),
          h2: ({ children }) => {
            const id = slugifyHeading(children);
            return (
              <h2
                id={id}
                className="scroll-mt-24 text-xl md:text-[24px] font-semibold text-ink-primary tracking-tight mt-8 mb-3 flex items-center gap-2.5"
              >
                <span className="h-2.5 w-2.5 rounded-full bg-accent inline-block shrink-0" />
                <span>{children}</span>
              </h2>
            );
          },
          h3: ({ children }) => (
            <h3 className="text-[18px] font-semibold text-ink-primary mt-6 mb-2">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="font-semibold text-brand mt-4 mb-2 uppercase tracking-wider text-xs">
              {children}
            </h4>
          ),
          p: ({ children }) => (
            <p className="text-ink-primary leading-7 text-[15px] md:text-base my-4 font-normal">
              {children}
            </p>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-ink-primary">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="text-ink-primary italic">{children}</em>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-6 space-y-2.5 my-4 text-ink-primary text-[15px] md:text-base leading-7">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-6 space-y-2.5 my-4 text-ink-primary text-[15px] md:text-base leading-7">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed marker:text-accent">{children}</li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-accent bg-brand-soft rounded-r-[12px] px-5 py-3.5 my-5 text-ink-primary border-y border-r border-brand-soft-border not-italic">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="my-6 overflow-x-auto rounded-[12px] border border-line bg-surface shadow-sm">
              <table className="w-full text-left border-collapse text-sm my-0">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-subtle text-ink-primary text-xs font-semibold uppercase tracking-wider border-b border-line">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-line text-ink-primary">{children}</tbody>
          ),
          tr: ({ children }) => (
            <tr className="hover:bg-hoverbg transition-colors">{children}</tr>
          ),
          th: ({ children }) => (
            <th className="px-4 py-3 font-semibold text-ink-primary">{children}</th>
          ),
          td: ({ children }) => (
            <td className="px-4 py-3 text-ink-primary align-top">{children}</td>
          ),
          code: ({ node, inline, className, children, ...props }: any) => {
            const match = /language-([\w-]+)/.exec(className || '');
            if (!inline && match) {
              return <CodeBlock language={match[1]}>{children}</CodeBlock>;
            }
            if (!inline && String(children).includes('\n')) {
              return <CodeBlock>{children}</CodeBlock>;
            }
            return (
              <code
                className="px-1.5 py-0.5 rounded bg-brand-soft text-brand font-mono text-xs border border-brand-soft-border font-medium"
                {...props}
              >
                {children}
              </code>
            );
          },
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:text-accent-hover underline underline-offset-4 font-medium transition-colors"
            >
              {children}
            </a>
          ),
          hr: () => <hr className="border-line my-8" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};
