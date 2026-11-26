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
    <section className="mt-8 rounded-2xl border border-indigo-500/25 bg-slate-950/80 p-5 md:p-6 space-y-5 shadow-xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">
            Interactive Architecture Explorer
          </span>
          <h3 className="text-lg font-bold text-white flex items-center gap-2 mt-0.5">
            <GitBranch className="h-5 w-5 text-indigo-400" />
            <span>{diagram.title}</span>
          </h3>
          {diagram.subtitle && <p className="text-xs text-slate-400 mt-0.5">{diagram.subtitle}</p>}
        </div>
        <span className="inline-flex items-center gap-1.5 text-xs text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 px-3 py-1 rounded-full self-start">
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
                className={`px-4 py-3 rounded-xl border text-left transition-all ${
                  isSelected
                    ? 'bg-indigo-600 text-white border-indigo-400 shadow-lg shadow-indigo-600/30 scale-[1.02]'
                    : 'bg-slate-900 text-slate-200 border-slate-700 hover:border-indigo-500/50 hover:bg-slate-800'
                }`}
              >
                <p className="text-[10px] uppercase font-bold tracking-wider opacity-75">
                  Stage {idx + 1}
                </p>
                <p className="text-sm font-bold">{node.label}</p>
              </button>
              {idx < diagram.nodes.length - 1 && (
                <ArrowRight className="h-4 w-4 text-indigo-400 shrink-0" />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Selected Component Inspector */}
      <div className="p-4 md:p-5 rounded-xl bg-slate-900/90 border border-slate-800 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">
            Responsibility
          </p>
          <p className="text-white font-semibold mt-1">{activeNode.role}</p>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-cyan-400">
            What Enters
          </p>
          <p className="text-slate-200 mt-1">{activeNode.input}</p>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
            Internal Processing
          </p>
          <p className="text-slate-200 mt-1">{activeNode.process}</p>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
            What Leaves
          </p>
          <p className="text-slate-200 mt-1">{activeNode.output}</p>
        </div>
      </div>
    </section>
  );
};
