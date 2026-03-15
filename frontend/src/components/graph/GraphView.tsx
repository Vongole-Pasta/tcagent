"use client";

import React, { useCallback, useEffect, useState } from 'react';
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
import * as d3 from 'd3-force';
import dagre from 'dagre';
import { useStore } from '@/store/useStore';

const nodeWidth = 200;
const nodeHeight = 60;

const getHierarchicalLayout = (nodes: Node[], edges: Edge[], selectedNodeId: string | null, neighbors: Set<string>, focusedNodeId: string | null) => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({ 
        rankdir: 'TB',
        nodesep: 80, // Tighter horizontal spacing
        ranksep: 120, // Slightly more vertical spacing to clarify hierarchy
        ranker: 'tight-tree' // Better at keeping parent/children together
    });

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        const isSelected = node.id === selectedNodeId;
        const nodeType = node.data?.type;
        const isNeighbor = neighbors.has(node.id);
        const isFocusActive = focusedNodeId !== null;

        let bgColor = '#ffffff';
        let borderColor = '#e2e8f0';

        if (isFocusActive && !isNeighbor && node.id !== focusedNodeId) {
            // Non-neighbors in focus mode get gray background
            bgColor = '#f8fafc';
            borderColor = '#f1f5f9';
        } else {
            if (nodeType === 'ENDPOINT') {
                bgColor = '#eff6ff';
                borderColor = '#3b82f6';
            } else if (nodeType === 'EXTERNAL_CALL') {
                bgColor = '#fff7ed';
                borderColor = '#f59e0b';
            }

            if (isSelected) {
                bgColor = '#fff1f2';
                borderColor = '#e11d48';
            }
        }

        return {
            ...node,
            position: {
                x: nodeWithPosition.x - nodeWidth / 2,
                y: nodeWithPosition.y - nodeHeight / 2,
            },
            style: {
                width: nodeWidth,
                borderRadius: '8px',
                padding: '10px',
                fontSize: '12px',
                fontWeight: 500,
                color: (isFocusActive && !isNeighbor && node.id !== focusedNodeId) ? '#94a3b8' : '#1e293b',
                backgroundColor: bgColor,
                border: isSelected ? `2px solid ${borderColor}` : `1px solid ${borderColor}`,
                boxShadow: isSelected ? '0 0 10px rgba(225, 29, 72, 0.2)' : '0 1px 3px rgba(0,0,0,0.1)',
                zIndex: isSelected ? 10 : 1,
                transition: 'all 0.3s ease'
            }
        };
    });

    return { nodes: layoutedNodes, edges };
};

const getForceLayout = (nodes: Node[], edges: Edge[], selectedNodeId: string | null) => {
    const simulationNodes = nodes.map(n => ({
        id: n.id,
        x: n.id === selectedNodeId ? 0 : (Math.random() - 0.5) * 500,
        y: n.id === selectedNodeId ? 0 : (Math.random() - 0.5) * 500,
        fx: n.id === selectedNodeId ? 0 : undefined,
        fy: n.id === selectedNodeId ? 0 : undefined,
    }));

    const simulationLinks = edges.map(e => ({
        source: e.source,
        target: e.target
    }));

    const simulation = d3.forceSimulation(simulationNodes as any)
        .force('link', d3.forceLink(simulationLinks).id((d: any) => d.id).distance(250))
        .force('charge', d3.forceManyBody().strength(-1000))
        .force('center', d3.forceCenter(0, 0))
        .force('collision', d3.forceCollide().radius(150))
        .stop();

    for (let i = 0; i < 300; ++i) simulation.tick();

    const layoutedNodes = nodes.map((node) => {
        const simNode = simulationNodes.find(n => n.id === node.id)!;
        const isSelected = node.id === selectedNodeId;
        const nodeType = node.data?.type;

        let bgColor = '#ffffff';
        let borderColor = '#e2e8f0';

        if (nodeType === 'ENDPOINT') {
            bgColor = '#eff6ff';
            borderColor = '#3b82f6';
        } else if (nodeType === 'EXTERNAL_CALL') {
            bgColor = '#fff7ed';
            borderColor = '#f59e0b';
        }

        if (isSelected) {
            bgColor = '#fff1f2';
            borderColor = '#e11d48';
        }

        return {
            ...node,
            position: {
                x: simNode.x! - nodeWidth / 2,
                y: simNode.y! - nodeHeight / 2,
            },
            style: {
                width: nodeWidth,
                borderRadius: '8px',
                padding: '10px',
                fontSize: '12px',
                fontWeight: 500,
                color: '#1e293b',
                backgroundColor: bgColor,
                border: isSelected ? `2px solid ${borderColor}` : `1px solid ${borderColor}`,
                boxShadow: isSelected ? '0 0 10px rgba(225, 29, 72, 0.2)' : '0 1px 3px rgba(0,0,0,0.1)',
                zIndex: isSelected ? 10 : 1
            }
        };
    });

    return { nodes: layoutedNodes, edges };
};

function InnerGraphView() {
    const { graphData, isLoading, fetchNodeDetail, selectedNodeId, projectNodes } = useStore();
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const [displayMode, setDisplayMode] = useState<'normal' | 'extended'>('normal');
    const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
    const { fitView } = useReactFlow();

    // Reset focus when data changes (e.g., selecting a new method from sidebar)
    useEffect(() => {
        setFocusedNodeId(null);
    }, [graphData]);

    useEffect(() => {
        if (graphData.nodes.length > 0) {
            // 1. Filter nodes based on mode
            // 'normal' (일반): Only METHOD nodes
            // 'extended' (확장): METHOD + EXTERNAL_CALL (effectively all)
            const filteredApiNodes = displayMode === 'normal' 
                ? graphData.nodes.filter(n => (n as any).type !== 'EXTERNAL_CALL')
                : graphData.nodes;

            const filteredApiNodeIds = new Set(filteredApiNodes.map(n => n.id));

            // 2. Filter edges to only include those between remaining nodes
            const filteredApiEdges = graphData.edges.filter(e => 
                filteredApiNodeIds.has(e.source) && filteredApiNodeIds.has(e.target)
            );

            // 3. Focus Logic: Identify neighbors
            const neighbors = new Set<string>();
            if (focusedNodeId) {
                neighbors.add(focusedNodeId);
                filteredApiEdges.forEach(e => {
                    if (e.source === focusedNodeId) neighbors.add(e.target);
                    if (e.target === focusedNodeId) neighbors.add(e.source);
                });
            }

            // 4. Map to React Flow Nodes
            const rfNodes: Node[] = filteredApiNodes.map(n => {
                const nodeType = (n as any).type;
                const className = (n as any).className || 'External';
                const name = (n as any).name;
                
                let label = name;
                if (nodeType === 'METHOD') {
                    label = `${name}()`;
                } else if (nodeType === 'EXTERNAL_CALL') {
                    label = `[Ext] ${name}`;
                }

                return {
                    id: n.id,
                    data: {
                        label: (
                            <div className="flex flex-col text-left overflow-hidden">
                                {className && (
                                    <span className="text-[10px] text-slate-500 truncate" title={className}>
                                        {className}
                                    </span>
                                )}
                                <span className="font-semibold truncate" title={label}>
                                    {label}
                                </span>
                            </div>
                        ),
                        type: nodeType
                    },
                    position: { x: 0, y: 0 },
                };
            });

            // 5. Map to React Flow Edges
            // 'normal' is always hierarchical -> smoothstep
            // 'extended' previously switched to force layout for > 10 nodes
            // User request: "Show Extended graph in hierarchical too"
            const useHierarchical = true; 
            const edgeType = useHierarchical ? 'smoothstep' : 'simplebezier';

            const rfEdges: Edge[] = filteredApiEdges.map(e => ({
                id: e.id,
                source: e.source,
                target: e.target,
                type: edgeType,
                animated: true,
                markerEnd: { x: 0, y: 0, type: MarkerType.ArrowClosed, color: '#94a3b8' },
                style: { stroke: '#cbd5e1', strokeWidth: 2 }
            }));

            // 6. Apply Layout
            const { nodes: layoutedNodes, edges: layoutedEdges } = useHierarchical
                ? getHierarchicalLayout(rfNodes, rfEdges, selectedNodeId, neighbors, focusedNodeId)
                : getForceLayout(rfNodes, rfEdges, selectedNodeId);

            setNodes(layoutedNodes);
            setEdges(layoutedEdges);

            if (!focusedNodeId) {
                window.requestAnimationFrame(() => {
                    fitView({ duration: 400, padding: 0.2 });
                });
            }
        } else {
            setNodes([]);
            setEdges([]);
        }
    }, [graphData, setNodes, setEdges, fitView, selectedNodeId, projectNodes, displayMode, focusedNodeId]);

    const onNodeClick = useCallback((event: any, node: Node) => {
        fetchNodeDetail(node.id);
    }, [fetchNodeDetail]);

    const onNodeDoubleClick = useCallback((event: any, node: Node) => {
        setFocusedNodeId(prev => prev === node.id ? null : node.id);
    }, []);

    const onPaneClick = useCallback(() => {
        setFocusedNodeId(null);
    }, []);

    return (
        <div className="flex-1 h-full bg-slate-50 relative">
            {isLoading && (
                <div className="absolute top-4 left-4 z-10 bg-white/80 p-2 rounded shadow text-sm">
                    Loading Graph...
                </div>
            )}
            
            {/* Focus Instruction */}
            {focusedNodeId && (
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 bg-slate-900 text-white px-4 py-2 rounded-full text-xs font-medium shadow-lg animate-bounce">
                    Double-click node or click background to reset focus
                </div>
            )}

            {/* Mode Toggles & Stats */}
            <div className="absolute top-4 left-4 z-10 flex items-center gap-3">
                <div className="flex bg-white rounded-lg shadow-sm border border-slate-200 p-1">
                    <button
                        onClick={() => setDisplayMode('normal')}
                        className={`px-4 py-2 text-xs font-semibold rounded-md transition-all ${
                            displayMode === 'normal' 
                                ? 'bg-slate-900 text-white shadow-sm' 
                                : 'text-slate-500 hover:text-slate-900 hover:bg-slate-50'
                        }`}
                    >
                        일반
                    </button>
                    <button
                        onClick={() => setDisplayMode('extended')}
                        className={`px-4 py-2 text-xs font-semibold rounded-md transition-all ${
                            displayMode === 'extended' 
                                ? 'bg-slate-900 text-white shadow-sm' 
                                : 'text-slate-500 hover:text-slate-900 hover:bg-slate-50'
                        }`}
                    >
                        확장
                    </button>
                </div>

                {/* Node Counts */}
                <div className="flex items-center gap-2 bg-white/90 px-3 py-2 rounded-lg shadow-sm border border-slate-200 text-[11px] font-medium text-slate-600">
                    <div className="flex items-center gap-1.5 px-1.5 border-r border-slate-100 last:border-0">
                        <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                        <span className="text-slate-400">엔드포인트:</span>
                        <span className="text-slate-700">{nodes.filter(n => n.data?.type === 'ENDPOINT').length}</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-1.5 border-r border-slate-100 last:border-0">
                        <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                        <span className="text-slate-400">메서드:</span>
                        <span className="text-slate-700">{nodes.filter(n => n.data?.type === 'METHOD').length}</span>
                    </div>
                    {displayMode === 'extended' && (
                        <div className="flex items-center gap-1.5 px-1.5 last:border-0">
                            <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                            <span className="text-slate-400">외부호출:</span>
                            <span className="text-slate-700">{nodes.filter(n => n.data?.type === 'EXTERNAL_CALL').length}</span>
                        </div>
                    )}
                </div>
            </div>

            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                onNodeDoubleClick={onNodeDoubleClick}
                onPaneClick={onPaneClick}
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
