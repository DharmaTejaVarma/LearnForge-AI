import React, { useState } from 'react';
import { ArchitectureDiagramData } from '../../services/courseService';
import { GitBranch, ArrowRight, MousePointerClick } from 'lucide-react';

interface InteractiveArchitectureDiagramProps {
  diagram: ArchitectureDiagramData;
}

export const InteractiveArchitectureDiagram: React.FC<InteractiveArchitectureDiagramProps> = ({
  diagram,
}) => {
  const [selectedId, setSelectedId] = useState<string>(diagram.nodes?.[0]?.id || '');

  if (!diagram || !diagram.nodes || diagram.nodes.length === 0) return null;

  const activeNode = diagram.nodes.find((n) => n.id === selectedId) || diagram.nodes[0];

  return (
    <section className="mt-8 rounded-[12px] border border-brand-soft-border bg-subtle p-5 md:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-accent">
            Interactive Architecture Explorer
          </span>
          <h3 className="lf-heading-card flex items-center gap-2 mt-0.5">
            <GitBranch className="h-5 w-5 text-brand" />
            <span>{diagram.title}</span>
          </h3>
          {diagram.subtitle && <p className="text-xs text-ink-secondary mt-0.5">{diagram.subtitle}</p>}
        </div>
        <span className="inline-flex items-center gap-1.5 text-xs text-brand bg-brand-soft border border-brand-soft-border px-3 py-1 rounded-full self-start font-medium">
          <MousePointerClick className="h-3.5 w-3.5" />
          Select a component
        </span>
      </div>

      {/* Connected Component Flow Bar */}
      <div className="flex flex-wrap items-center gap-2.5 py-2">
        {diagram.nodes.map((node, idx) => {
          const isSelected = node.id === activeNode.id;
          return (
            <React.Fragment key={node.id}>
              <button
                type="button"
                onClick={() => setSelectedId(node.id)}
                className={`px-4 py-3 rounded-[10px] border text-left transition-all ${
                  isSelected
                    ? 'bg-brand text-white border-brand shadow-card scale-[1.02]'
                    : 'bg-surface text-ink-primary border-line hover:border-brand-soft-border hover:bg-hoverbg'
                }`}
              >
                <p className="text-[10px] uppercase font-bold tracking-wider opacity-80">
                  Stage {idx + 1}
                </p>
                <p className="text-sm font-bold">{node.label}</p>
              </button>
              {idx < diagram.nodes.length - 1 && (
                <ArrowRight className="h-4 w-4 text-accent shrink-0" />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Selected Component Inspector */}
      <div className="p-4 md:p-5 rounded-[12px] bg-surface border border-line grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-brand">
            Responsibility
          </p>
          <p className="text-ink-primary font-semibold mt-1">{activeNode.role}</p>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-accent">
            What Enters
          </p>
          <p className="text-ink-primary mt-1">{activeNode.input}</p>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-status-success-text">
            Internal Processing
          </p>
          <p className="text-ink-primary mt-1">{activeNode.process}</p>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-status-warning-text">
            What Leaves
          </p>
          <p className="text-ink-primary mt-1">{activeNode.output}</p>
        </div>
      </div>
    </section>
  );
};
