"use client";

import React, { useEffect, useState } from 'react';
import { useStore } from '@/store/useStore';
import { useDropzone } from 'react-dropzone';
import { Upload, Search, Box, Globe, FileCode, CheckSquare, Square, PlayCircle, Loader2, FileText, X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { Separator } from '@/components/ui/separator';


export function Sidebar() {
    const {
        projectNodes,
        fetchProjectNodes,
        uploadFiles,
        selectedNodeId,
        fetchUpstreamGraph,
        fetchDownstreamGraph,
        projects,
        fetchProjects,
        selectedProject,
        selectProject,
        selectedMethodIds,
        toggleMethodSelection,
        setSelectedMethodIds, // Added for 'All Check' feature
        generateHappyCaseScenarios,
        isAgentRunning,
        setViewMode,
        viewMode // Added for potential future use or consistency
    } = useStore();

    const [search, setSearch] = useState('');
    const [isSelectionModalOpen, setIsSelectionModalOpen] = useState(false);


    useEffect(() => {
        fetchProjectNodes();
        fetchProjects();
    }, [fetchProjectNodes, fetchProjects]);

    const onDrop = (acceptedFiles: File[]) => {
        uploadFiles(acceptedFiles);
    };

    const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

    const filteredNodes = projectNodes.filter(n => {
        return n.name.toLowerCase().includes(search.toLowerCase()) ||
            (n.endpoint && n.endpoint.toLowerCase().includes(search.toLowerCase()));
    });

    const sortedNodes = [...filteredNodes].sort((a, b) => {
        const getScore = (s?: string | null) => {
            if (s === 'DELETED') return 3;
            if (s === 'NEW') return 2;
            if (s === 'MODIFIED' || s === 'TO-BE' || s === 'TOBE') return 1;
            return 0;
        };
        const scoreA = getScore(a.status);
        const scoreB = getScore(b.status);

        if (scoreA !== scoreB) return scoreB - scoreA; // Higher priority first
        return a.name.localeCompare(b.name);
    });

    const selectedMethods = projectNodes
        .filter(n => selectedMethodIds.map(String).includes(String(n.id)))
        .sort((a, b) => a.name.localeCompare(b.name)); // Alphabetical ascending (A-Z)

    const handleNodeClick = (node: any) => {
        const nodeId = String(node.id);
        if (node.type === 'ENDPOINT') {
            fetchDownstreamGraph(nodeId);
        } else {
            fetchUpstreamGraph(nodeId);
        }
        setViewMode('graph');
    };

    const getStatusBadge = (status?: string | null) => {
        if (!status || status === 'AS-IS') return null;

        let label = '';
        let colorClass = '';

        switch (status) {
            case 'NEW':
                label = 'NEW';
                colorClass = 'bg-green-500 hover:bg-green-600';
                break;
            case 'MODIFIED':
            case 'TO-BE':
            case 'TOBE':
                label = 'MODIFIED';
                colorClass = 'bg-blue-500 hover:bg-blue-600';
                break;
            case 'DELETED':
                label = 'DELETED';
                colorClass = 'bg-red-500 hover:bg-red-600';
                break;
            default:
                return null;
        }

        return (
            <Badge
                variant="default"
                className={cn("text-[10px] h-5 px-1.5 pointer-events-none", colorClass)}
            >
                {label}
            </Badge>
        );
    };

    return (
        <div className="w-full h-full flex flex-col bg-background overflow-hidden">
            {/* Project Selector */}
            <div className="p-4 border-b shrink-0 space-y-2">
                <label className="text-xs font-semibold text-muted-foreground">Target Project</label>
                <select
                    className="flex h-9 w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    value={selectedProject || ''}
                    onChange={(e) => selectProject(e.target.value || null)}
                >
                    <option value="">+ New Project (Auto-detect)</option>
                    {projects.map(p => (
                        <option key={p} value={p}>{p}</option>
                    ))}
                </select>
            </div>

            {/* Upload Area */}
            <div className="p-4 border-b shrink-0">
                <div
                    {...getRootProps()}
                    className={cn(
                        "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
                        isDragActive ? "border-primary bg-primary/10" : "border-muted-foreground/25 hover:border-primary/50"
                    )}
                >
                    <input {...getInputProps()} />
                    <Upload className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">
                        {isDragActive ? "Drop project here..." : "Drag & drop project (Zip)"}
                    </p>
                </div>
            </div>

            {/* Controls: Search */}
            <div className="p-4 border-b shrink-0 space-y-3">
                <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search methods..."
                        className="pl-8"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
                
                {/* All Check Feature */}
                {sortedNodes.length > 0 && (
                    <div 
                        className="flex items-center gap-2 px-1 py-1 cursor-pointer group/all"
                        onClick={() => {
                            const filteredIds = sortedNodes.map(n => String(n.id));
                            const allSelected = filteredIds.every(id => selectedMethodIds.includes(id));
                            
                            if (allSelected) {
                                // Deselect only the currently filtered items
                                setSelectedMethodIds(selectedMethodIds.filter(id => !filteredIds.includes(id)));
                            } else {
                                // Select all currently filtered items (keeping existing selections outside the filter)
                                const newSelection = Array.from(new Set([...selectedMethodIds, ...filteredIds]));
                                setSelectedMethodIds(newSelection);
                            }
                        }}
                    >
                        <div className="flex items-center justify-center w-6 h-6 hover:bg-zinc-200 dark:hover:bg-zinc-800 rounded transition-colors">
                            {sortedNodes.every(n => selectedMethodIds.includes(String(n.id))) ? (
                                <CheckSquare className="h-4 w-4 text-primary" />
                            ) : (
                                <Square className="h-4 w-4 text-muted-foreground/60" />
                            )}
                        </div>
                        <span className="text-[11px] font-medium text-muted-foreground group-hover/all:text-foreground transition-colors select-none">
                            All Check ({sortedNodes.length})
                        </span>
                    </div>
                )}
            </div>

            {/* List */}
            <ScrollArea className="flex-1 min-h-0">
                <div className="p-2 space-y-1 pb-4">
                    {sortedNodes.length === 0 && (
                        <div className="p-4 text-center text-sm text-muted-foreground">
                            No items found.
                        </div>
                    )}
                    {sortedNodes.map((node) => {
                        const isSelected = selectedMethodIds.map(String).includes(String(node.id));
                        return (
                            <div
                                key={node.id}
                                className={cn(
                                    "flex items-center gap-2 p-2 rounded-md cursor-pointer transition-colors text-sm border border-transparent group",
                                    selectedNodeId === node.id
                                        ? "bg-accent text-accent-foreground border-border shadow-sm"
                                        : isSelected
                                            ? "bg-primary/5 hover:bg-primary/10 border-primary/20"
                                            : "hover:bg-muted/60",
                                    node.status === 'DELETED' && "opacity-60 grayscale"
                                )}
                            >
                                {/* Checkbox for multi-selection - Expanded Click Area */}
                                <div
                                    className="flex items-center justify-center w-8 h-8 hover:bg-accent rounded-md transition-colors shrink-0"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        toggleMethodSelection(String(node.id));
                                    }}
                                >
                                    {isSelected ? (
                                        <CheckSquare className="h-5 w-5 text-primary" />
                                    ) : (
                                        <Square className="h-5 w-5 text-muted-foreground/60" />
                                    )}
                                </div>

                                <div className="flex-1 flex items-center gap-2 min-w-0" onClick={() => handleNodeClick(node)}>
                                    {node.type === 'ENDPOINT' ? (
                                        <Globe className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                                    ) : (
                                        <Box className="h-3.5 w-3.5 text-orange-500 shrink-0" />
                                    )}

                                    <div className="flex-1 min-w-0 flex flex-col justify-center py-0.5">
                                        {node.class_name && (
                                            <span className="text-[10px] text-muted-foreground leading-none mb-1 truncate block opacity-75 font-mono">
                                                {node.class_name}
                                            </span>
                                        )}
                                        <div className="flex items-center gap-2">
                                            <span className="truncate block font-medium leading-none">
                                                {node.name}
                                            </span>
                                            {getStatusBadge(node.status)}
                                        </div>
                                        {node.endpoint && (
                                            <span className="text-[10px] text-muted-foreground truncate block mt-1">
                                                {node.http_method} {node.endpoint}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </ScrollArea>

            {/* Happy Case Generation Button */}
            <div className="p-4 border-t bg-muted/50 shrink-0 space-y-3">
                <div className="flex items-center justify-between px-1">
                    <div className="flex items-center gap-1.5 relative">
                        <span className="text-xs font-medium text-muted-foreground">
                            Selected: <span className="text-foreground">{selectedMethodIds.length}</span>
                        </span>
                        {selectedMethodIds.length > 0 && (
                            <>
                                <button
                                    onClick={() => setIsSelectionModalOpen(!isSelectionModalOpen)}
                                    className={cn(
                                        "p-1.5 rounded-md transition-all shadow-sm",
                                        isSelectionModalOpen ? "bg-primary text-primary-foreground scale-110" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                                    )}
                                    title="선택된 메서드 관리"
                                >
                                    <FileText className="h-4 w-4" />
                                </button>

                                {/* Backdrop for closing */}
                                {isSelectionModalOpen && (
                                    <div
                                        className="fixed inset-0 z-[90]"
                                        onClick={() => setIsSelectionModalOpen(false)}
                                    />
                                )}

                                {/* Persistent Selection Manager */}
                                <div className={cn(
                                    "absolute bottom-full left-0 mb-4 w-[270px] bg-zinc-100 dark:bg-zinc-900 text-popover-foreground border border-border shadow-2xl rounded-xl transition-all duration-300 z-[100] overflow-hidden",
                                    isSelectionModalOpen ? "opacity-100 translate-y-0 visible" : "opacity-0 translate-y-4 invisible pointer-events-none"
                                )}>
                                    <div className="text-[12px] font-bold border-b border-border/50 flex items-center justify-between bg-zinc-200/50 dark:bg-zinc-800/50 p-3.5">
                                        <div className="flex items-center gap-2">
                                            <FileText className="h-4 w-4 text-primary" />
                                            <span className="text-zinc-700 dark:text-zinc-200">선택 목록 ({selectedMethodIds.length})</span>
                                        </div>
                                        <button
                                            onClick={() => setIsSelectionModalOpen(false)}
                                            className="p-1.5 hover:bg-zinc-300 dark:hover:bg-zinc-700 rounded-lg transition-colors text-zinc-500 dark:text-zinc-400"
                                        >
                                            <X className="h-4 w-4" />
                                        </button>
                                    </div>
                                    <div className="max-h-[350px] overflow-y-auto custom-scrollbar">
                                        <div className="p-3 space-y-2.5">
                                            {selectedMethods.length === 0 && (
                                                <div className="text-center py-10 text-muted-foreground text-[11px] italic">
                                                    선택된 항목이 없습니다.
                                                </div>
                                            )}
                                            {selectedMethods.map((m) => (
                                                <div key={m.id} className="group/item flex items-start justify-between gap-3 p-2.5 rounded-lg bg-white dark:bg-zinc-800/40 border border-zinc-200/60 dark:border-zinc-700/60 hover:border-primary/30 transition-all shadow-sm">
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 mb-1.5">
                                                            {m.type === 'ENDPOINT' ? (
                                                                <Globe className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                                                            ) : (
                                                                <Box className="h-3.5 w-3.5 text-orange-500 shrink-0" />
                                                            )}
                                                            {m.type === 'ENDPOINT' && (
                                                                <span className="text-blue-600 dark:text-blue-400 font-mono text-[9px] font-semibold truncate bg-blue-500/5 px-1 rounded">
                                                                    {m.http_method} {m.endpoint}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <span className="font-semibold text-zinc-800 dark:text-zinc-200 break-all font-mono text-[11px] block leading-tight">
                                                            {m.name}
                                                        </span>
                                                    </div>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            toggleMethodSelection(String(m.id));
                                                        }}
                                                        className="mt-0.5 p-1.5 text-red-500 hover:text-white hover:bg-red-500 rounded-md transition-all opacity-100 group-hover/item:scale-110"
                                                        title="선택 해제"
                                                    >
                                                        <X className="h-4 w-4" />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    {/* Arrow */}
                                    <div className="absolute -bottom-1 left-6 w-2.5 h-2.5 bg-zinc-100 dark:bg-zinc-900 border-r border-b border-border rotate-45"></div>
                                </div>
                            </>
                        )}
                    </div>
                    {selectedMethodIds.length > 0 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-[10px] px-2"
                            onClick={() => {
                                selectedMethodIds.forEach(id => toggleMethodSelection(id));
                            }}
                        >
                            Reset
                        </Button>
                    )}
                </div>
                <Button
                    variant={selectedMethodIds.length > 0 ? "default" : "secondary"}
                    className="w-full gap-2 shadow-md font-semibold"
                    disabled={selectedMethodIds.length === 0 || isAgentRunning}
                    onClick={() => generateHappyCaseScenarios()}
                >
                    {isAgentRunning ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <PlayCircle className="h-4 w-4" />
                    )}
                    {isAgentRunning ? 'Generating...' : 'Happy Case 생성'}
                </Button>
            </div>
        </div>
    );
}
