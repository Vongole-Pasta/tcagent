"use client";

import React from 'react';
import { useStore } from '@/store/useStore';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Button } from '@/components/ui/button';
import { Sparkles, Loader2, Code2 } from 'lucide-react';
import { IntegrationScenarioView } from '../agent/IntegrationScenarioView';

export function DetailPanel() {
    const { 
        selectedNodeDetail, 
        selectedNodeId, 
        generateIntegrationScenario, 
        isAgentRunning,
        integrationScenarios,
        clearScenarios
    } = useStore();

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

    const handleGenerate = () => {
        if (selectedNodeId) {
            generateIntegrationScenario(selectedNodeId);
        }
    };

    return (
        <div className="h-full flex flex-col bg-background min-h-0 overflow-hidden">
            <div className="p-4 border-b shrink-0 flex items-center justify-between gap-4 bg-muted/5">
                <div className="min-w-0 flex-1">
                    <h2 className="font-semibold text-lg truncate">
                        {selectedNodeDetail.name}{selectedNodeDetail.type === 'METHOD' ? '()' : ''}
                    </h2>
                    {selectedNodeDetail.signature && (
                        <code className="text-[10px] text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded mt-1 block truncate">
                            {selectedNodeDetail.signature}
                        </code>
                    )}
                </div>
                
                <div className="flex shrink-0 gap-2">
                    <Button 
                        size="sm" 
                        variant="default"
                        className="bg-blue-600 hover:bg-blue-700 h-9 px-3 gap-2"
                        onClick={handleGenerate}
                        disabled={isAgentRunning}
                    >
                        {isAgentRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                        <span className="hidden sm:inline">통합 시나리오 생성</span>
                    </Button>
                </div>
            </div>

            {/* Using native div for robust scrolling */}
            <div className="flex-1 overflow-auto min-h-0 w-full">
                {/* 1. Integration Scenario Area (Show only when running or results exist) */}
                {(isAgentRunning || integrationScenarios.length > 0) && (
                    <div className="border-b bg-blue-50/10">
                        <div className="p-2 px-4 flex items-center justify-between border-b bg-blue-50/20">
                            <span className="text-xs font-bold text-blue-600 flex items-center gap-1">
                                <Sparkles className="h-3 w-3" /> Agent Analysis
                            </span>
                            <Button variant="ghost" size="xs" className="h-6 text-[10px]" onClick={clearScenarios}>
                                Clear
                            </Button>
                        </div>
                        <IntegrationScenarioView />
                    </div>
                )}

                {/* 2. Source Code Area */}
                <div className="p-0 relative">
                    <div className="sticky top-0 z-10 bg-background/80 backdrop-blur-sm px-4 py-1.5 border-b flex items-center gap-2 text-[11px] font-medium text-muted-foreground">
                        <Code2 className="h-3 w-3" /> Source Code
                    </div>
                    {selectedNodeDetail.source ? (
                        <SyntaxHighlighter
                            language="java"
                            style={vscDarkPlus}
                            customStyle={{ margin: 0, borderRadius: 0, fontSize: '13px', paddingTop: '10px' }}
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
