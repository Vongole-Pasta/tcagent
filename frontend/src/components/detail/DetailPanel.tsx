"use client";

import React, { useState, useEffect } from 'react';
import { useStore } from '@/store/useStore';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Button } from '@/components/ui/button';
import { Code2, Diff } from 'lucide-react';
import { DiffView } from './DiffView';

export function DetailPanel() {
    const {
        selectedNodeDetail,
        selectedNodeId,
        projectNodes,
        codeSnapshots
    } = useStore();

    if (!selectedNodeId) {
        return (
            <div className="h-full flex items-center justify-center text-muted-foreground text-sm p-4 bg-background">
                그래프에서 노드를 선택하면 상세 정보를 볼 수 있습니다.
            </div>
        );
    }

    if (!selectedNodeDetail) {
        return (
            <div className="h-full flex items-center justify-center text-muted-foreground text-sm p-4 bg-background">
                상세 정보를 불러오는 중...
            </div>
        );
    }

    // 현재 노드의 상태 확인 (MODIFIED 여부)
    const currentNode = projectNodes.find(n => n.id === selectedNodeId);
    const isModified = currentNode?.status === 'MODIFIED';
    const oldSource = selectedNodeDetail.signature ? codeSnapshots[selectedNodeDetail.signature] : null;
    const canShowDiff = isModified && oldSource && oldSource !== selectedNodeDetail.source;


    return (
        <div className="h-full flex flex-col bg-background min-h-0 overflow-hidden">
            <div className="p-4 border-b shrink-0 flex items-center justify-between gap-4 bg-muted/5">
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                        <h2 className="font-semibold text-lg truncate">
                            {selectedNodeDetail.name}{selectedNodeDetail.type === 'METHOD' ? '()' : ''}
                        </h2>
                        {currentNode?.status && (
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${currentNode.status === 'NEW' ? 'bg-green-500/10 text-green-500' :
                                currentNode.status === 'MODIFIED' ? 'bg-blue-500/10 text-blue-500' :
                                    'bg-muted text-muted-foreground'
                                }`}>
                                {currentNode.status}
                            </span>
                        )}
                    </div>
                    {selectedNodeDetail.signature && (
                        <code className="text-[10px] text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded mt-1 block truncate">
                            {selectedNodeDetail.signature}
                        </code>
                    )}
                </div>

            </div>

            <div className="flex-1 overflow-auto min-h-0 w-full">

                {/* 2. Source Code / Diff Area */}
                <div className="p-0 relative">
                    <div className="sticky top-0 z-10 bg-background/80 backdrop-blur-sm px-4 py-1.5 border-b flex items-center gap-2 text-[11px] font-medium text-muted-foreground">
                        {canShowDiff ? <Diff className="h-3 w-3 text-orange-500" /> : <Code2 className="h-3 w-3" />}
                        {canShowDiff ? 'Source Comparison (Diff)' : 'Source Code'}
                    </div>

                    {canShowDiff && oldSource ? (
                        <div className="p-2">
                            <DiffView oldCode={oldSource} newCode={selectedNodeDetail.source} />
                        </div>
                    ) : selectedNodeDetail.source ? (
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
                            소스 코드를 사용할 수 없습니다.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
