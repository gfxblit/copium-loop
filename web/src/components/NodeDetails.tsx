import type { NodeState } from '../types';
import { X, Terminal, Clock, ShieldCheck, Cpu } from 'lucide-react';
import { clsx } from 'clsx';

interface NodeDetailsProps {
  nodeId: string | null;
  nodeState: NodeState | null;
  onClose: () => void;
}

const NodeDetails = ({ nodeId, nodeState, onClose }: NodeDetailsProps) => {
  if (!nodeId) return null;

  return (
    <div className={clsx(
      "fixed inset-y-0 right-0 w-full md:w-[500px] bg-white shadow-2xl z-50 transform transition-transform duration-300 flex flex-col border-l border-gray-200",
      nodeId ? "translate-x-0" : "translate-x-full"
    )}>
      <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-gray-50">
        <div className="flex items-center gap-2">
          <Cpu className="w-5 h-5 text-blue-500" />
          <h2 className="text-xl font-bold uppercase tracking-tight text-gray-800">{nodeId}</h2>
        </div>
        <button 
          onClick={onClose}
          className="p-1 hover:bg-gray-200 rounded-full transition-colors"
        >
          <X className="w-6 h-6 text-gray-500" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50/30">
        {nodeState ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white p-3 rounded-lg border border-gray-100 shadow-sm">
                <div className="text-xs text-gray-400 uppercase font-semibold mb-1 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> Status
                </div>
                <div className="font-bold text-gray-700 capitalize">{nodeState.status}</div>
              </div>
              <div className="bg-white p-3 rounded-lg border border-gray-100 shadow-sm">
                <div className="text-xs text-gray-400 uppercase font-semibold mb-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Last Active
                </div>
                <div className="font-mono text-sm text-gray-600">
                  {new Date(nodeState.lastUpdated).toLocaleTimeString()}
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-xs text-gray-400 uppercase font-semibold flex items-center gap-1 px-1">
                <Terminal className="w-3 h-3" /> Live Logs
              </div>
              <div className="bg-slate-900 rounded-lg p-3 font-mono text-sm overflow-hidden border border-slate-800 shadow-inner">
                {nodeState.logs.length === 0 ? (
                  <div className="text-slate-500 italic">No logs available for this node.</div>
                ) : (
                  <div className="space-y-1.5 max-h-[600px] overflow-y-auto custom-scrollbar">
                    {nodeState.logs.map((log, i) => (
                      <div key={i} className="flex gap-2">
                        <span className="text-slate-500 shrink-0 select-none">
                          {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
                        </span>
                        <span className={clsx(
                          "break-all",
                          log.event_type === 'status' ? "text-blue-400 font-bold" :
                          log.event_type === 'error' ? "text-red-400" :
                          log.source === 'llm' ? "text-emerald-400" : "text-slate-300"
                        )}>
                          {log.event_type === 'status' ? `STATUS: ${String(log.data)}` : 
                           log.event_type === 'info' ? `INFO: ${String(log.data)}` :
                           String(log.data)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 italic">
            Waiting for node activity...
          </div>
        )}
      </div>

      <style>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #334155;
          border-radius: 2px;
        }
      `}</style>
    </div>
  );
};

export default NodeDetails;
