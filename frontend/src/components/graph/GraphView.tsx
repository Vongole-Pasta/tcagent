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
    dagreGraph.setGraph({ rankdir: direction }); // Use the passed direction

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
    const { graphData, isLoading, fetchNodeDetail, selectedNodeId, projectNodes } = useStore();
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow(); // Added useReactFlow hook

    useEffect(() => {
        if (graphData.nodes.length > 0) {
            // Determine layout direction based on selected node type
            const selectedNode = projectNodes.find(n => n.id === selectedNodeId);
            // User feedback: "Bottom-Up" means Me at Bottom, Callers at Top. 
            // Since edges are Caller->Me, 'TB' layout achieves this (Source Top, Target Bottom).
            // So we use 'TB' for BOTH Upstream and Downstream.
            const direction = 'TB';

            // Map API data to React Flow format if not already
            // Map API data to React Flow format if not already
            const rfNodes: Node[] = graphData.nodes.map(n => {
                const isSelected = n.id === selectedNodeId;
                const isEndpoint = (n as any).type === 'ENDPOINT';

                return {
                    id: n.id,
                    data: {
                        label: isEndpoint ? (n as any).name : `${(n as any).name}()`, // Requirement 3: Append ()
                        type: (n as any).type
                    },
                    position: { x: 0, y: 0 },
                    style: {
                        // Requirement 4: Highlighting (Modified per user request: Uniform default style)
                        background: '#ffffff',
                        border: isSelected
                            ? '2px solid #ef4444'
                            : '1px solid #e2e8f0',
                        borderRadius: '8px',
                        padding: '10px',
                        fontSize: '12px',
                        fontWeight: isSelected ? 700 : 500,
                        color: '#1e293b',
                        boxShadow: isSelected ? '0 0 15px rgba(239, 68, 68, 0.3)' : 'none',
                        zIndex: isSelected ? 10 : 1,
                        width: nodeWidth // Ensure width is consistent for layout
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
                style: { stroke: '#94a3b8' } // Softer edge color
            }));

            const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
                rfNodes,
                rfEdges,
                direction // Pass the determined direction
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
    }, [graphData, setNodes, setEdges, fitView, selectedNodeId, projectNodes]); // Added fitView, selectedNodeId, projectNodes to dependencies

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
