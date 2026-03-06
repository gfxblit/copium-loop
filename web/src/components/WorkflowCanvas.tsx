import { useMemo } from 'react';
import ReactFlow, { 
  Background, 
  Controls, 
  MiniMap,
  MarkerType
} from 'reactflow';
import type { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import AgentNode from './AgentNode';
import type { NodeState } from '../types';

const nodeTypes = {
  agent: AgentNode,
};

interface WorkflowCanvasProps {
  nodeStates: Record<string, NodeState>;
  onNodeSelect: (nodeId: string | null) => void;
}

const WorkflowCanvas = ({ nodeStates, onNodeSelect }: WorkflowCanvasProps) => {
  // Define the graph structure based on LangGraph in src/copium_loop/graph.py
  const initialNodes: Node[] = useMemo(() => [
    { id: 'coder', type: 'agent', position: { x: 250, y: 50 }, data: { label: 'Coder', state: nodeStates['coder'] } },
    { id: 'tester', type: 'agent', position: { x: 250, y: 150 }, data: { label: 'Tester', state: nodeStates['tester'] } },
    { id: 'architect', type: 'agent', position: { x: 250, y: 250 }, data: { label: 'Architect', state: nodeStates['architect'] } },
    { id: 'reviewer', type: 'agent', position: { x: 250, y: 350 }, data: { label: 'Reviewer', state: nodeStates['reviewer'] } },
    { id: 'pr_pre_checker', type: 'agent', position: { x: 250, y: 450 }, data: { label: 'PR Pre-Checker', state: nodeStates['pr_pre_checker'] } },
    { id: 'journaler', type: 'agent', position: { x: 250, y: 550 }, data: { label: 'Journaler', state: nodeStates['journaler'] } },
    { id: 'pr_creator', type: 'agent', position: { x: 250, y: 650 }, data: { label: 'PR Creator', state: nodeStates['pr_creator'] } },
  ], [nodeStates]);

  const initialEdges: Edge[] = [
    { id: 'e1-2', source: 'coder', target: 'tester', animated: nodeStates['coder']?.status === 'active', markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e2-3', source: 'tester', target: 'architect', animated: nodeStates['tester']?.status === 'active', markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e3-4', source: 'architect', target: 'reviewer', animated: nodeStates['architect']?.status === 'active', markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e4-5', source: 'reviewer', target: 'pr_pre_checker', animated: nodeStates['reviewer']?.status === 'active', markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e5-6', source: 'pr_pre_checker', target: 'journaler', animated: nodeStates['pr_pre_checker']?.status === 'active', markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e6-7', source: 'journaler', target: 'pr_creator', animated: nodeStates['journaler']?.status === 'active', markerEnd: { type: MarkerType.ArrowClosed } },
    
    // Conditional back-edges
    { id: 'e2-1', source: 'tester', target: 'coder', label: 'fail', style: { stroke: '#ef4444' }, animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
    { id: 'e4-3', source: 'reviewer', target: 'architect', label: 'reject', style: { stroke: '#ef4444' }, animated: true, markerEnd: { type: MarkerType.ArrowClosed } },
  ];

  return (
    <div className="w-full h-full bg-slate-50">
      <ReactFlow
        nodes={initialNodes}
        edges={initialEdges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onNodeSelect(node.id)}
        onPaneClick={() => onNodeSelect(null)}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
};

export default WorkflowCanvas;
