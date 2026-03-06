import { memo } from 'react';
import { Handle, Position } from 'reactflow';
import type { NodeState, NodeStatus } from '../types';
import { CheckCircle2, XCircle, AlertCircle, Loader2, PlayCircle, Clock } from 'lucide-react';
import { clsx } from 'clsx';

const statusColors: Record<NodeStatus, string> = {
  active: 'bg-blue-50 border-blue-500 text-blue-700',
  success: 'bg-green-50 border-green-500 text-green-700',
  approved: 'bg-green-50 border-green-500 text-green-700',
  failed: 'bg-red-50 border-red-500 text-red-700',
  rejected: 'bg-red-50 border-red-500 text-red-700',
  error: 'bg-red-50 border-red-500 text-red-700',
  idle: 'bg-gray-50 border-gray-300 text-gray-700',
  pending: 'bg-gray-50 border-gray-200 text-gray-400',
  journaled: 'bg-purple-50 border-purple-500 text-purple-700',
};

const statusIcons = {
  active: <Loader2 className="w-4 h-4 animate-spin" />,
  success: <CheckCircle2 className="w-4 h-4" />,
  approved: <CheckCircle2 className="w-4 h-4" />,
  failed: <XCircle className="w-4 h-4" />,
  rejected: <XCircle className="w-4 h-4" />,
  error: <AlertCircle className="w-4 h-4" />,
  idle: <PlayCircle className="w-4 h-4 opacity-50" />,
  pending: <Clock className="w-4 h-4 opacity-50" />,
  journaled: <CheckCircle2 className="w-4 h-4" />,
};

interface AgentNodeProps {
  data: {
    label: string;
    state?: NodeState;
    selected?: boolean;
  };
}

const AgentNode = ({ data }: AgentNodeProps) => {
  const status = data.state?.status || 'pending';
  const colorClass = statusColors[status] || statusColors.pending;

  return (
    <div className={clsx(
      "px-4 py-2 shadow-md rounded-md bg-white border-2 transition-all duration-300 min-w-[150px]",
      colorClass,
      data.selected ? "ring-2 ring-offset-2 ring-blue-400" : ""
    )}>
      <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-gray-400" />
      
      <div className="flex items-center justify-between gap-2">
        <div className="font-bold text-sm uppercase tracking-wider">{data.label}</div>
        <div>{statusIcons[status]}</div>
      </div>
      
      {status === 'active' && (
        <div className="mt-2 h-1 w-full bg-blue-100 rounded-full overflow-hidden">
          <div className="h-full bg-blue-500 animate-[loading_1s_ease-in-out_infinite] w-1/2"></div>
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-gray-400" />
      
      <style>{`
        @keyframes loading {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(200%); }
        }
      `}</style>
    </div>
  );
};

export default memo(AgentNode);
