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

const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({ rankdir: 'LR' }); // Left to Right layout

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
                width: nodeWidth,
                // Access custom data property type safely
                backgroundColor: (node.data?.type === 'ENDPOINT') ? '#eff6ff' : '#fff',
                border: (node.data?.type === 'ENDPOINT') ? '1px solid #3b82f6' : '1px solid #777'
            }
        };
    });

    return { nodes: layoutedNodes, edges };
};

function InnerGraphView() { // Renamed from GraphView
    const { graphData, isLoading, fetchNodeDetail } = useStore();
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow(); // Added useReactFlow hook

    useEffect(() => {
        if (graphData.nodes.length > 0) {
            // Map API data to React Flow format if not already
            const rfNodes: Node[] = graphData.nodes.map(n => ({
                id: n.id,
                data: {
                    label: (n as any).name,
                    type: (n as any).type // Store type in data so we can access it later
                },
                position: { x: 0, y: 0 },
                style: {
                    background: (n as any).type === 'ENDPOINT' ? '#eff6ff' : '#ffffff',
                    border: (n as any).type === 'ENDPOINT' ? '1px solid #2563eb' : '1px solid #e2e8f0',
                    borderRadius: '8px',
                    padding: '10px',
                    fontSize: '12px',
                    fontWeight: 500,
                    color: '#1e293b'
                }
            }));

            const rfEdges: Edge[] = graphData.edges.map(e => ({
                id: e.id,
                source: e.source,
                target: e.target,
                type: 'smoothstep',
                animated: true,
                markerEnd: { x: 0, y: 0, type: MarkerType.ArrowClosed },
            }));

            const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
                rfNodes,
                rfEdges
            );

            setNodes(layoutedNodes);
            setEdges(layoutedEdges);

            // Force fit view after layout
            window.requestAnimationFrame(() => {
                fitView({ duration: 400, padding: 0.2 });
            });
        } else {
            setNodes([]);
            setEdges([]);
        }
    }, [graphData, setNodes, setEdges, fitView]); // Added fitView to dependencies

    const onNodeClick = useCallback((event: any, node: Node) => {
        fetchNodeDetail(node.id);
    }, [fetchNodeDetail]);

    return (
        <div className="flex-1 h-full bg-slate-50 relative">
            {isLoading && (
                <div className="absolute top-4 left-4 z-10 bg-white/80 p-2 rounded shadow text-sm">
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
