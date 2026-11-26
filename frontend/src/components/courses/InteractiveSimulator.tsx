import React, { useState } from 'react';
import { SimulatorConfigData } from '../../services/courseService';
import { Button } from '../common/Button';
import { Play, Activity, Layers, Server, CheckCircle2, AlertTriangle } from 'lucide-react';

interface InteractiveSimulatorProps {
  simulator: SimulatorConfigData;
}

const HTTP_METHOD_INFO: Record<string, { crud: string; safe: string; desc: string }> = {
  GET: { crud: 'Read', safe: 'Yes (Read-only)', desc: 'Retrieves a creature or list without modifying server state.' },
  POST: { crud: 'Create', safe: 'No', desc: 'Creates a new creature record from the JSON request body.' },
  PUT: { crud: 'Replace', safe: 'Idempotent', desc: 'Completely replaces an existing creature resource at /creatures/{name}.' },
  PATCH: { crud: 'Update', safe: 'No', desc: 'Partially modifies only the supplied fields of an existing creature.' },
  DELETE: { crud: 'Delete', safe: 'Idempotent', desc: 'Removes the target creature resource from the store.' },
};

export const InteractiveSimulator: React.FC<InteractiveSimulatorProps> = ({ simulator }) => {
  // HTTP Simulator State
  const [method, setMethod] = useState<string>(simulator.default_method || 'GET');
  const [endpoint, setEndpoint] = useState<string>(simulator.default_endpoint || '/creatures');
  const [queryParam, setQueryParam] = useState<string>('');
  const [bodyText, setBodyText] = useState<string>(
    JSON.stringify({ name: 'Nessie', country: 'UK', area: 'Loch Ness', aka: 'Loch Ness Monster' }, null, 2),
  );
  const [creatures, setCreatures] = useState<Record<string, any>>({
    yeti: { name: 'Yeti', country: 'CN', area: 'Himalayas', aka: 'Abominable Snowman' },
    bigfoot: { name: 'Bigfoot', country: 'US', area: 'Pacific Northwest', aka: 'Sasquatch' },
  });
  const [simResponse, setSimResponse] = useState<{
    status: number;
    statusText: string;
    body: any;
    trace: string[];
  } | null>(null);

  // Layered Simulator State
  const [layerPattern, setLayerPattern] = useState<'clean' | 'bypass'>('clean');

  // Concurrency Simulator State
  const [reqCount, setReqCount] = useState<number>(4);
  const [ioLatency, setIoLatency] = useState<number>(120);

  // API Communication Pattern State
  const [commPattern, setCommPattern] = useState<'library' | 'rpc' | 'http' | 'pubsub' | 'queue'>('http');

  if (!simulator) return null;

  const runHttpSimulation = () => {
    const cleanPath = endpoint.trim().split('?')[0] || '/creatures';
    const parts = cleanPath.replace(/^\/+|\/+$/g, '').split('/');
    const trace = [
      `1. Client sends ${method} ${cleanPath}${queryParam ? `?${queryParam}` : ''}`,
      `2. Web Layer parses URL parts=${JSON.stringify(parts)} & validates contract`,
    ];

    if (parts[0] !== 'creatures') {
      setSimResponse({
        status: 404,
        statusText: 'Not Found',
        body: { detail: `Unknown route '${cleanPath}'. Try '/creatures' or '/creatures/yeti'.` },
        trace: [...trace, '3. Router found no matching endpoint -> returns HTTP 404'],
      });
      return;
    }

    const targetKey = parts[1]?.toLowerCase();

    if (method === 'GET') {
      if (!targetKey) {
        let items = Object.values(creatures);
        if (queryParam.includes('=')) {
          const [qk, qv] = queryParam.split('=');
          items = items.filter((c) => String(c[qk.trim()] || '').toLowerCase() === qv.trim().toLowerCase());
        }
        setSimResponse({
          status: 200,
          statusText: 'OK',
          body: items,
          trace: [...trace, `3. Service Layer read ${items.length} record(s) -> returns 200 OK JSON`],
        });
      } else if (creatures[targetKey]) {
        setSimResponse({
          status: 200,
          statusText: 'OK',
          body: creatures[targetKey],
          trace: [...trace, `3. Data Layer located '${targetKey}' -> returns 200 OK JSON`],
        });
      } else {
        setSimResponse({
          status: 404,
          statusText: 'Not Found',
          body: { detail: `Creature '${parts[1]}' not found` },
          trace: [...trace, `3. Data Layer returned None -> Web Layer raises 404 Not Found`],
        });
      }
      return;
    }

    if (method === 'POST') {
      try {
        const parsed = JSON.parse(bodyText);
        if (!parsed.name || !parsed.country) {
          setSimResponse({
            status: 422,
            statusText: 'Unprocessable Entity',
            body: { detail: "Validation error: 'name' and 'country' are required strings." },
            trace: [...trace, '3. Pydantic validation rejected incomplete payload -> HTTP 422'],
          });
          return;
        }
        const key = String(parsed.name).toLowerCase();
        setCreatures((prev) => ({ ...prev, [key]: parsed }));
        setSimResponse({
          status: 201,
          statusText: 'Created',
          body: parsed,
          trace: [...trace, `3. Service validated model & Data Layer stored '${parsed.name}' -> 201 Created`],
        });
      } catch {
        setSimResponse({
          status: 400,
          statusText: 'Bad Request',
          body: { detail: 'Invalid JSON syntax in request body.' },
          trace: [...trace, '3. JSON parser failed -> HTTP 400 Bad Request'],
        });
      }
      return;
    }

    if (method === 'PATCH' || method === 'PUT') {
      if (!targetKey || !creatures[targetKey]) {
        setSimResponse({
          status: 404,
          statusText: 'Not Found',
          body: { detail: "Specify an existing '/creatures/{name}' (e.g. '/creatures/yeti')." },
          trace: [...trace, '3. Target resource missing -> HTTP 404'],
        });
        return;
      }
      try {
        const parsed = JSON.parse(bodyText);
        const updated = method === 'PUT' ? parsed : { ...creatures[targetKey], ...parsed };
        setCreatures((prev) => ({ ...prev, [targetKey]: updated }));
        setSimResponse({
          status: 200,
          statusText: 'OK',
          body: updated,
          trace: [...trace, `3. Service executed ${method} on '${targetKey}' -> 200 OK`],
        });
      } catch {
        setSimResponse({
          status: 400,
          statusText: 'Bad Request',
          body: { detail: 'Invalid JSON request body.' },
          trace: [...trace, '3. JSON parser failed -> HTTP 400'],
        });
      }
      return;
    }

    if (method === 'DELETE') {
      if (!targetKey || !creatures[targetKey]) {
        setSimResponse({
          status: 404,
          statusText: 'Not Found',
          body: { detail: "Creature not found. Try '/creatures/bigfoot'." },
          trace: [...trace, '3. Resource not found -> HTTP 404'],
        });
        return;
      }
      setCreatures((prev) => {
        const next = { ...prev };
        delete next[targetKey];
        return next;
      });
      setSimResponse({
        status: 200,
        statusText: 'OK',
        body: { deleted: targetKey },
        trace: [...trace, `3. Data Layer deleted '${targetKey}' -> 200 OK`],
      });
    }
  };

  if (simulator.type === 'api_communication') {
    const patterns: Record<
      'library' | 'rpc' | 'http' | 'pubsub' | 'queue',
      {
        label: string;
        boundary: string;
        coupling: string;
        blocking: string;
        steps: string[];
        tradeoff: string;
      }
    > = {
      library: {
        label: 'Library Function Call',
        boundary: 'In-process (same memory space)',
        coupling: 'Tight (same language & runtime)',
        blocking: 'Synchronous call stack',
        steps: [
          '1. Caller invokes `format_creature("Yeti")` directly in Python.',
          '2. Arguments are passed by reference in local memory — zero network serialization.',
          '3. Function returns Python dict or raises local exception immediately.',
        ],
        tradeoff: 'Fastest (nanoseconds), but cannot scale or deploy separately across machines.',
      },
      rpc: {
        label: 'Remote Procedure Call (RPC)',
        boundary: 'Network (client stub -> server stub)',
        coupling: 'Method-oriented contract (e.g., gRPC / protobuf)',
        blocking: 'Usually synchronous request/reply',
        steps: [
          '1. Client calls local stub `get_creature("Yeti")`, which looks like a normal function.',
          '2. Stub serializes parameters and sends them over TCP/HTTP2 to remote service.',
          '3. Remote server executes procedure and returns serialized result to client stub.',
        ],
        tradeoff: 'Familiar function-call ergonomics across networks, but tighter coupling to method signatures.',
      },
      http: {
        label: 'Request-Response (HTTP/REST)',
        boundary: 'Network (Client <-> Web Service)',
        coupling: 'Loose (URL + HTTP Verb + JSON contract)',
        blocking: 'Client waits for response (or awaits asynchronously)',
        steps: [
          '1. Client sends `GET /creatures/yeti` with Accept: application/json.',
          '2. FastAPI validates path/headers and calls Service Layer.',
          '3. Server returns `200 OK` + JSON body (or `404` / `422` on error).',
        ],
        tradeoff: 'Universal web standard with caching & clear status codes; ideal for frontend-backend APIs.',
      },
      pubsub: {
        label: 'Publish-Subscribe (Pub-Sub)',
        boundary: 'Event Broker / Topic Channel',
        coupling: 'Decoupled (publisher does not know subscribers)',
        blocking: 'Non-blocking fire-and-forget broadcast',
        steps: [
          '1. Publisher emits event `creature.sighted` to a topic on the broker.',
          '2. Broker broadcasts a copy of the event to ALL subscribed consumers.',
          '3. Analytics, notifications, and audit services react independently.',
        ],
        tradeoff: 'Great for event fan-out to multiple listeners; harder to trace end-to-end.',
      },
      queue: {
        label: 'Message Queue (Work Distribution)',
        boundary: 'Queue Broker -> Competing Workers',
        coupling: 'Decoupled producer & worker pool',
        blocking: 'Asynchronous (producer returns immediately)',
        steps: [
          '1. Web API enqueues job `{"task": "send_alert", "creature": "Yeti"}`.',
          '2. Queue delivers the message to EXACTLY ONE available worker.',
          '3. Worker processes the slow task in the background without blocking HTTP.',
        ],
        tradeoff: 'Smooths traffic spikes and ensures each job runs once across competing workers.',
      },
    };
    const active = patterns[commPattern];
    return (
      <section className="mt-8 rounded-2xl border border-indigo-500/25 bg-slate-950/85 p-5 md:p-6 space-y-4 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">
              Simulated Environment · API Communication
            </span>
            <h3 className="text-lg font-bold text-white flex items-center gap-2 mt-0.5">
              <Server className="h-5 w-5 text-indigo-400" />
              <span>{simulator.title}</span>
            </h3>
            {simulator.description && <p className="text-xs text-slate-400 mt-0.5">{simulator.description}</p>}
          </div>
          <span className="px-2.5 py-1 rounded-full bg-slate-900 border border-slate-700 text-[11px] text-slate-400">
            In-Browser Simulation
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          {(Object.keys(patterns) as Array<keyof typeof patterns>).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setCommPattern(k)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                commPattern === k
                  ? 'bg-indigo-600 text-white border-indigo-400'
                  : 'bg-slate-900 text-slate-300 border-slate-700 hover:border-slate-600'
              }`}
            >
              {patterns[k].label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
            <span className="text-slate-400 block">Boundary</span>
            <strong className="text-slate-100">{active.boundary}</strong>
          </div>
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
            <span className="text-slate-400 block">Contract / Coupling</span>
            <strong className="text-slate-100">{active.coupling}</strong>
          </div>
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
            <span className="text-slate-400 block">Execution Style</span>
            <strong className="text-slate-100">{active.blocking}</strong>
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 space-y-2 text-xs text-slate-200">
          {active.steps.map((s, idx) => (
            <p key={idx} className="font-mono text-indigo-200">{s}</p>
          ))}
          <p className="text-slate-400 pt-2 border-t border-slate-800">
            <strong className="text-emerald-300">Trade-off:</strong> {active.tradeoff}
          </p>
        </div>
      </section>
    );
  }

  if (simulator.type === 'layered_architecture') {
    return (
      <section className="mt-8 rounded-2xl border border-cyan-500/25 bg-slate-950/85 p-5 md:p-6 space-y-4">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-cyan-400">
            Interactive Simulation
          </span>
          <h3 className="text-lg font-bold text-white flex items-center gap-2 mt-0.5">
            <Layers className="h-5 w-5 text-cyan-400" />
            <span>{simulator.title}</span>
          </h3>
          {simulator.description && <p className="text-xs text-slate-400 mt-1">{simulator.description}</p>}
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setLayerPattern('clean')}
            className={`px-4 py-2 rounded-xl text-xs font-semibold border transition-all ${
              layerPattern === 'clean'
                ? 'bg-emerald-600/25 border-emerald-500 text-emerald-200'
                : 'bg-slate-900 border-slate-700 text-slate-300'
            }`}
          >
            Recommended: Web -&gt; Service -&gt; Data
          </button>
          <button
            type="button"
            onClick={() => setLayerPattern('bypass')}
            className={`px-4 py-2 rounded-xl text-xs font-semibold border transition-all ${
              layerPattern === 'bypass'
                ? 'bg-rose-600/25 border-rose-500 text-rose-200'
                : 'bg-slate-900 border-slate-700 text-slate-300'
            }`}
          >
            Anti-Pattern: Web -&gt; Direct DB Query
          </button>
        </div>

        {layerPattern === 'clean' ? (
          <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/30 space-y-2 text-sm">
            <div className="flex items-center gap-2 font-bold text-emerald-300">
              <CheckCircle2 className="h-4 w-4" />
              Clean Information Hiding
            </div>
            <p className="text-slate-200 text-xs md:text-sm leading-relaxed">
              1. <strong>Web Layer</strong> validates HTTP params &amp; Pydantic models.<br />
              2. <strong>Service Layer</strong> applies domain rules cleanly without importing HTTP/SQL drivers.<br />
              3. <strong>Data Layer</strong> swaps SQLite/PostgreSQL freely while returning consistent domain Models.
            </p>
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-rose-950/25 border border-rose-500/30 space-y-2 text-sm">
            <div className="flex items-center gap-2 font-bold text-rose-300">
              <AlertTriangle className="h-4 w-4" />
              Layer Violation Detected
            </div>
            <p className="text-slate-200 text-xs md:text-sm leading-relaxed">
              Embedding raw SQL inside FastAPI route handlers couples transport to persistence, leaks database secrets if unprojected, and duplicates validation logic whenever a CLI or background job needs the same operation.
            </p>
          </div>
        )}
      </section>
    );
  }

  if (simulator.type === 'concurrency_trace') {
    const syncTotal = reqCount * ioLatency;
    const asyncTotal = Math.round(ioLatency * 1.15);
    const speedup = (syncTotal / asyncTotal).toFixed(1);
    return (
      <section className="mt-8 rounded-2xl border border-indigo-500/25 bg-slate-950/85 p-5 md:p-6 space-y-4">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">
            Interactive Simulation
          </span>
          <h3 className="text-lg font-bold text-white flex items-center gap-2 mt-0.5">
            <Activity className="h-5 w-5 text-indigo-400" />
            <span>{simulator.title}</span>
          </h3>
          {simulator.description && <p className="text-xs text-slate-400 mt-1">{simulator.description}</p>}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
            <div className="flex justify-between text-xs text-slate-300">
              <span>Concurrent I/O Requests</span>
              <strong className="text-white">{reqCount}</strong>
            </div>
            <input
              type="range"
              min={2}
              max={8}
              value={reqCount}
              onChange={(e) => setReqCount(Number(e.target.value))}
              className="w-full accent-indigo-500"
            />
          </div>
          <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
            <div className="flex justify-between text-xs text-slate-300">
              <span>Per-Request Network/DB Wait</span>
              <strong className="text-white">{ioLatency} ms</strong>
            </div>
            <input
              type="range"
              min={50}
              max={300}
              step={10}
              value={ioLatency}
              onChange={(e) => setIoLatency(Number(e.target.value))}
              className="w-full accent-indigo-500"
            />
          </div>
        </div>

        <div className="space-y-3 pt-1">
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-amber-300 font-semibold">Synchronous Sequential</span>
              <span className="text-slate-300 font-mono">{syncTotal} ms</span>
            </div>
            <div className="h-3 rounded-full bg-slate-900 overflow-hidden">
              <div className="h-full bg-amber-500 rounded-full w-full" />
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-emerald-300 font-semibold">Async Event Loop (`await`)</span>
              <span className="text-slate-300 font-mono">~{asyncTotal} ms ({speedup}x faster throughput)</span>
            </div>
            <div className="h-3 rounded-full bg-slate-900 overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all"
                style={{ width: `${Math.min(100, Math.round((asyncTotal / syncTotal) * 100))}%` }}
              />
            </div>
          </div>
        </div>
      </section>
    );
  }

  // Default: HTTP Request + REST Method Explorer Simulator
  const methodMeta = HTTP_METHOD_INFO[method] || HTTP_METHOD_INFO.GET;

  return (
    <section className="mt-8 rounded-2xl border border-indigo-500/25 bg-slate-950/85 p-5 md:p-6 space-y-5 shadow-xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">
            Interactive Experiment
          </span>
          <h3 className="text-lg font-bold text-white flex items-center gap-2 mt-0.5">
            <Server className="h-5 w-5 text-indigo-400" />
            <span>{simulator.title}</span>
          </h3>
          {simulator.description && <p className="text-xs text-slate-400 mt-0.5">{simulator.description}</p>}
        </div>
        <span className="px-3 py-1 rounded-full bg-slate-900 border border-slate-700 text-xs text-slate-300 font-mono">
          CRUD: <strong className="text-indigo-300">{methodMeta.crud}</strong> · Safe: {methodMeta.safe}
        </span>
      </div>

      {/* REST Verb Selector Pills */}
      <div className="flex flex-wrap gap-2">
        {Object.keys(HTTP_METHOD_INFO).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => {
              setMethod(m);
              if ((m === 'PATCH' || m === 'PUT' || m === 'DELETE') && endpoint === '/creatures') {
                setEndpoint('/creatures/yeti');
              } else if (m === 'POST') {
                setEndpoint('/creatures');
              }
            }}
            className={`px-3.5 py-1.5 rounded-lg font-mono text-xs font-bold border transition-all ${
              method === m
                ? 'bg-indigo-600 text-white border-indigo-400'
                : 'bg-slate-900 text-slate-300 border-slate-700 hover:border-slate-600'
            }`}
          >
            {m}
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-400">{methodMeta.desc}</p>

      {/* Endpoint & Query Inputs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="sm:col-span-2">
          <label className="block text-[11px] font-semibold text-slate-400 mb-1">Endpoint Path</label>
          <input
            type="text"
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            placeholder="/creatures or /creatures/yeti"
            className="w-full rounded-xl bg-slate-900 border border-slate-700 px-3.5 py-2 font-mono text-xs md:text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-[11px] font-semibold text-slate-400 mb-1">Query Params (optional)</label>
          <input
            type="text"
            value={queryParam}
            onChange={(e) => setQueryParam(e.target.value)}
            placeholder="country=CN"
            className="w-full rounded-xl bg-slate-900 border border-slate-700 px-3.5 py-2 font-mono text-xs md:text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
      </div>

      {(method === 'POST' || method === 'PUT' || method === 'PATCH') && (
        <div>
          <label className="block text-[11px] font-semibold text-slate-400 mb-1">JSON Request Body</label>
          <textarea
            rows={4}
            spellCheck={false}
            value={bodyText}
            onChange={(e) => setBodyText(e.target.value)}
            className="w-full rounded-xl bg-slate-900 border border-slate-700 p-3 font-mono text-xs text-emerald-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
      )}

      <div>
        <Button size="sm" variant="primary" onClick={runHttpSimulation} icon={<Play className="h-3.5 w-3.5" />}>
          Send Simulated Request
        </Button>
      </div>

      {simResponse && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-4 space-y-3 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span
              className={`px-2.5 py-1 rounded-md font-mono font-bold ${
                simResponse.status < 300
                  ? 'bg-emerald-500/20 text-emerald-300'
                  : 'bg-rose-500/20 text-rose-300'
              }`}
            >
              HTTP {simResponse.status} {simResponse.statusText}
            </span>
            <span className="font-mono text-slate-400">Content-Type: application/json</span>
          </div>
          <pre className="p-3 rounded-lg bg-slate-950 text-emerald-200 font-mono overflow-x-auto">
            {JSON.stringify(simResponse.body, null, 2)}
          </pre>
          <div className="space-y-1 text-slate-400 border-t border-slate-800 pt-2">
            {simResponse.trace.map((step, i) => (
              <p key={i}>{step}</p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};
