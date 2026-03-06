import { useState } from 'react';
import WorkflowCanvas from './components/WorkflowCanvas';
import NodeDetails from './components/NodeDetails';
import { useTelemetry } from './hooks/useTelemetry';
import { Activity, Wifi, WifiOff } from 'lucide-react';
import { clsx } from 'clsx';

function App() {
  const { nodeStates, workflowStatus, connected } = useTelemetry();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const selectedNodeState = selectedNodeId ? nodeStates[selectedNodeId] : null;

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-50 overflow-hidden font-sans">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between shadow-sm z-10">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 p-2 rounded-lg shadow-blue-200 shadow-lg">
            <Activity className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-black text-gray-900 tracking-tight leading-none uppercase">Copium Loop</h1>
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mt-1">Interactive Web Interface</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className={clsx(
            "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider transition-colors",
            connected ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
          )}>
            {connected ? (
              <><Wifi className="w-3 h-3" /> Live</>
            ) : (
              <><WifiOff className="w-3 h-3" /> Offline</>
            )}
          </div>
          
          <div className="flex flex-col items-end">
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-0.5">Workflow Status</div>
            <div className={clsx(
              "text-xs font-black uppercase tracking-wider",
              workflowStatus === 'success' ? "text-green-600" : 
              workflowStatus === 'failed' ? "text-red-600" : 
              "text-blue-600 animate-pulse"
            )}>
              {workflowStatus || 'Running'}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 relative flex overflow-hidden">
        <div className="flex-1 relative">
          <WorkflowCanvas 
            nodeStates={nodeStates} 
            onNodeSelect={setSelectedNodeId} 
          />
        </div>

        <NodeDetails 
          nodeId={selectedNodeId}
          nodeState={selectedNodeState}
          onClose={() => setSelectedNodeId(null)}
        />
      </main>

      {/* Mobile Footer Overlay */}
      <div className="md:hidden fixed bottom-4 left-4 right-4 z-40 bg-white/80 backdrop-blur p-3 rounded-2xl border border-white shadow-xl flex justify-between items-center">
         <div className="flex items-center gap-2">
           <Activity className="w-4 h-4 text-blue-600" />
           <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">Copium Loop</span>
         </div>
         <div className="text-[10px] font-mono text-gray-500 bg-gray-100 px-2 py-1 rounded">
           {Object.keys(nodeStates).length} Nodes Active
         </div>
      </div>
    </div>
  );
}

export default App;
