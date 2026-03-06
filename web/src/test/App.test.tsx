import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from '../App';
import { useTelemetry } from '../hooks/useTelemetry';

// Mock the hook
vi.mock('../hooks/useTelemetry', () => ({
  useTelemetry: vi.fn(),
}));

// Mock ReactFlow components that might fail in jsdom
vi.mock('reactflow', () => {
  const ReactFlowMock = ({ children }: { children: React.ReactNode }) => <div data-testid="react-flow">{children}</div>;
  return {
    default: ReactFlowMock,
    Background: () => <div data-testid="background" />,
    Controls: () => <div data-testid="controls" />,
    MiniMap: () => <div data-testid="minimap" />,
    MarkerType: { ArrowClosed: 'arrowclosed' },
  };
});

describe('App', () => {
  it('renders the application title', () => {
    vi.mocked(useTelemetry).mockReturnValue({
      events: [],
      nodeStates: {},
      workflowStatus: 'running',
      connected: true,
    });

    render(<App />);
    // We have multiple elements with "Copium Loop", check for the H1 specifically
    const titles = screen.getAllByText(/Copium Loop/i);
    expect(titles.length).toBeGreaterThan(0);
    expect(titles[0]).toBeInTheDocument();
  });

  it('shows the offline status when disconnected', () => {
    vi.mocked(useTelemetry).mockReturnValue({
      events: [],
      nodeStates: {},
      workflowStatus: 'running',
      connected: false,
    });
    
    render(<App />);
    expect(screen.getByText(/Offline/i)).toBeInTheDocument();
  });
});
