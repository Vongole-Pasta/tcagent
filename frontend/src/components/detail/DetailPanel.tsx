"use client";

import React from 'react';
import { useStore } from '@/store/useStore';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';


export function DetailPanel() {
    const { selectedNodeDetail, selectedNodeId } = useStore();

    if (!selectedNodeId) {
        return (
            <div className="h-full flex items-center justify-center text-muted-foreground text-sm p-4 bg-background">
                Select a node in the graph to view details
            </div>
        );
    }

    if (!selectedNodeDetail) {
        return (
            <div className="h-full flex items-center justify-center text-muted-foreground text-sm p-4 bg-background">
                Loading details...
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-background min-h-0 overflow-hidden">
            <div className="p-4 border-b shrink-0">
                <h2 className="font-semibold text-lg">{selectedNodeDetail.name}</h2>
                {selectedNodeDetail.signature && (
                    <code className="text-xs text-muted-foreground bg-muted p-1 rounded mt-1 block break-all">
                        {selectedNodeDetail.signature}
                    </code>
                )}
            </div>
            {/* Using native div for robust scrolling */}
            <div className="flex-1 overflow-auto min-h-0 w-full">
                <div className="p-0">
                    {selectedNodeDetail.source ? (
                        <SyntaxHighlighter
                            language="java"
                            style={vscDarkPlus}
                            customStyle={{ margin: 0, borderRadius: 0, fontSize: '13px' }}
                            showLineNumbers
                        >
                            {selectedNodeDetail.source}
                        </SyntaxHighlighter>
                    ) : (
                        <div className="p-4 text-sm text-muted-foreground">
                            No source code available.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
