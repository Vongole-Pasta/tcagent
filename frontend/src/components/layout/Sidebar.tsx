"use client";

import React, { useEffect, useState } from 'react';
import { useStore } from '@/store/useStore';
import { useDropzone } from 'react-dropzone';
import { Upload, Search, Box, Globe, FileCode } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';

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
        selectProject
    } = useStore();

    const [search, setSearch] = useState('');
    const [filterType, setFilterType] = useState<'METHOD' | 'ENDPOINT'>('METHOD');

    useEffect(() => {
        fetchProjectNodes();
        fetchProjects();
    }, [fetchProjectNodes, fetchProjects]);

    const onDrop = (acceptedFiles: File[]) => {
        uploadFiles(acceptedFiles);
    };

    const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

    const filteredNodes = projectNodes.filter(n => {
        const matchesSearch = n.name.toLowerCase().includes(search.toLowerCase()) ||
            (n.endpoint && n.endpoint.toLowerCase().includes(search.toLowerCase()));

        if (!matchesSearch) return false;

        // If 'METHOD' tab is selected, show ALL methods (including endpoints)
        if (filterType === 'METHOD') return true;

        // If 'ENDPOINT' tab is selected, show only endpoints
        return n.type === filterType;
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

    const handleNodeClick = (node: any) => {
        // ... (same as before)
        if (node.type === 'ENDPOINT') {
            fetchDownstreamGraph(node.id);
        } else {
            fetchUpstreamGraph(node.id);
        }
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
        <div className="w-full border-r h-full flex flex-col bg-background overflow-hidden relative">
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

            {/* Controls: Search + Tabs */}
            <div className="p-4 border-b space-y-3 shrink-0">
                <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search..."
                        className="pl-8"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>

                <Tabs value={filterType} onValueChange={(v) => setFilterType(v as any)} className="w-full">
                    <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="METHOD">Methods</TabsTrigger>
                        <TabsTrigger value="ENDPOINT">APIs</TabsTrigger>
                    </TabsList>
                </Tabs>
            </div>

            {/* List */}
            <ScrollArea className="flex-1 h-full">
                <div className="p-2 space-y-1 pb-4">
                    {sortedNodes.length === 0 && (
                        <div className="p-4 text-center text-sm text-muted-foreground">
                            No items found.
                        </div>
                    )}
                    {sortedNodes.map((node) => (
                        <div
                            key={node.id}
                            onClick={() => handleNodeClick(node)}
                            className={cn(
                                "flex items-center gap-3 p-3 rounded-md cursor-pointer transition-colors text-sm border border-transparent",
                                selectedNodeId === node.id
                                    ? "bg-accent text-accent-foreground border-border shadow-sm"
                                    : "hover:bg-muted/60",
                                node.status === 'DELETED' && "opacity-60 grayscale"
                            )}
                        >
                            {node.type === 'ENDPOINT' ? (
                                <Globe className="h-4 w-4 text-blue-500 shrink-0" />
                            ) : (
                                <Box className="h-4 w-4 text-orange-500 shrink-0" />
                            )}

                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                    <span className="font-mono text-xs text-muted-foreground mr-1">
                                        {node.type === 'ENDPOINT' ? 'API' : 'M'}
                                    </span>
                                    <div className="flex flex-col flex-1 min-w-0">

                                        <div className="flex items-center gap-2">
                                            <span className="truncate block font-medium">
                                                {node.name}
                                            </span>
                                            {getStatusBadge(node.status)}
                                        </div>
                                        {node.endpoint && (
                                            <span className="text-[10px] text-muted-foreground truncate block">
                                                {node.http_method} {node.endpoint}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </ScrollArea>
        </div>
    );
}
