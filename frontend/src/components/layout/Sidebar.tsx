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
        fetchDownstreamGraph
    } = useStore();

    const [search, setSearch] = useState('');
    const [filterType, setFilterType] = useState<'METHOD' | 'ENDPOINT'>('METHOD');

    useEffect(() => {
        fetchProjectNodes();
    }, [fetchProjectNodes]);

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

    const handleNodeClick = (node: any) => {
        if (node.type === 'ENDPOINT') {
            fetchDownstreamGraph(node.id);
        } else {
            fetchUpstreamGraph(node.id);
        }
    };

    return (
        <div className="w-full border-r h-full flex flex-col bg-background overflow-hidden relative">
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
                    {filteredNodes.length === 0 && (
                        <div className="p-4 text-center text-sm text-muted-foreground">
                            No items found.
                        </div>
                    )}
                    {filteredNodes.map((node) => (
                        <div
                            key={node.id}
                            onClick={() => handleNodeClick(node)}
                            className={cn(
                                "flex items-center gap-3 p-3 rounded-md cursor-pointer transition-colors text-sm border border-transparent",
                                selectedNodeId === node.id
                                    ? "bg-accent text-accent-foreground border-border shadow-sm"
                                    : "hover:bg-muted/60"
                            )}
                        >
                            {node.type === 'ENDPOINT' ? (
                                <Globe className="h-4 w-4 text-blue-500 shrink-0" />
                            ) : (
                                <Box className="h-4 w-4 text-orange-500 shrink-0" />
                            )}

                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-0.5">
                                    <span className="font-medium truncate block">
                                        {node.name}
                                    </span>
                                </div>
                                {node.type === 'ENDPOINT' && (
                                    <div className="flex items-center gap-2">
                                        <Badge variant="outline" className="text-[10px] h-4 px-1">
                                            {node.http_method || 'API'}
                                        </Badge>
                                        <div className="text-xs text-muted-foreground truncate font-mono">
                                            {node.endpoint}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </ScrollArea>
        </div>
    );
}
