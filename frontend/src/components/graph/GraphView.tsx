"use client";

import React, { useEffect, useCallback } from 'react';
import {
    ReactFlow,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
    ConnectionLineType,
    Node,
    Edge,
    ReactFlowProvider,
    useReactFlow
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { useStore } from '@/store/useStore';

const nodeWidth = 200;
const nodeHeight = 60;

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'TB') => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({ rankdir: direction });

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        return {
            ...node,
            position: {
                x: nodeWithPosition.x - nodeWidth / 2,
                y: nodeWithPosition.y - nodeHeight / 2,
            },
            style: {
                ...node.style,
                width: nodeWidth,
            }
        };
    });

    return { nodes: layoutedNodes, edges };
};

function InnerGraphView() { // Renamed from GraphView
    const { graphData, isGraphLoading, fetchNodeDetail, selectedNodeId, projectNodes } = useStore();
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();

    useEffect(() => {
        if (graphData.nodes.length > 0) {
            const direction = 'TB';

            const rfNodes: Node[] = graphData.nodes.map(n => {
                const isSelected = n.id === selectedNodeId;
                const isEndpoint = (n as any).type === 'ENDPOINT';
                const className = (n as any).className;
                const nodeName = isEndpoint ? (n as any).name : `${(n as any).name}()`;

                return {
                    id: n.id,
                    data: {
                        label: (
                            <div className="flex flex-col items-center justify-center h-full">
                                {className && (
                                    <div className="text-[10px] text-slate-500 font-semibold mb-1 leading-tight text-center w-full truncate px-1">
                                        {className}
                                    </div>
                                )}
                                <div className="font-bold text-sm text-center leading-tight">
                                    {nodeName}
                                </div>
                            </div>
                        ),
                        type: (n as any).type
                    },
                    position: { x: 0, y: 0 },
                    style: {
                        background: '#ffffff',
                        border: isSelected
                            ? '2px solid #ef4444'
                            : '1px solid #e2e8f0',
                        borderRadius: '8px',
                        padding: '10px', // Keep padding
                        fontSize: '12px',
                        color: '#1e293b',
                        boxShadow: isSelected ? '0 0 15px rgba(239, 68, 68, 0.3)' : '0 1px 3px rgba(0,0,0,0.1)',
                        zIndex: isSelected ? 10 : 1,
                        width: nodeWidth,
                        height: nodeHeight, // Enforce height
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }
                };
            });

            const rfEdges: Edge[] = graphData.edges.map(e => ({
                id: e.id,
                source: e.source,
                target: e.target,
                type: 'smoothstep',
                animated: true,
                markerEnd: { x: 0, y: 0, type: MarkerType.ArrowClosed },
                style: { stroke: '#94a3b8' }
            }));

            const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
                rfNodes,
                rfEdges,
                direction
            );

            setNodes(layoutedNodes);
            setEdges(layoutedEdges);

            window.requestAnimationFrame(() => {
                fitView({ duration: 400, padding: 0.2 });
            });
        } else {
            setNodes([]);
            setEdges([]);
        }
    }, [graphData, setNodes, setEdges, fitView, selectedNodeId, projectNodes]);

    const onNodeClick = useCallback((event: any, node: Node) => {
        fetchNodeDetail(node.id);
    }, [fetchNodeDetail]);

    return (
        <div className="flex-1 h-full bg-slate-50 relative">
            {isGraphLoading && (
                <div className="absolute top-4 left-4 z-10 bg-white/80 p-2 rounded shadow text-sm flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                    Loading Graph...
                </div>
            )}
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                fitView
            >
                <Background color="#ccc" gap={20} />
                <Controls />
            </ReactFlow>
        </div>
    );
}

export function GraphView() {
    return (
        <ReactFlowProvider>
            <InnerGraphView />
        </ReactFlowProvider>
    );
}
