"use client";

import React, { useState } from 'react';
import { useStore } from '@/store/useStore';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FlaskConical, Code2, CheckCircle2, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";

export function IntegrationScenarioView() {
    const { integrationScenarios, isAgentRunning, error, projectNodes } = useStore();
    const [openIndex, setOpenIndex] = useState<number | null>(0);

    const getMethodName = (methodId: string) => {
        const node = projectNodes.find(n => n.id === methodId);
        return node ? node.name : methodId;
    };

    if (isAgentRunning) {
        return (
            <div className="flex flex-col items-center justify-center p-12 space-y-4">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
                <p className="text-sm font-medium animate-pulse">에이전트가 소스코드와 영향 경로를 분석하여 시나리오를 작성 중입니다...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-8 flex items-center gap-3 text-destructive bg-destructive/10 rounded-lg m-4">
                <AlertCircle className="h-5 w-5" />
                <p className="text-sm font-medium">{error}</p>
            </div>
        );
    }

    if (integrationScenarios.length === 0) {
        return null;
    }

    return (
        <div className="p-4 space-y-6">
            <div className="flex items-center gap-2 mb-2">
                <FlaskConical className="h-5 w-5 text-primary" />
                <h2 className="text-xl font-bold">생성된 통합 테스트 시나리오</h2>
                <Badge variant="outline" className="ml-2">{integrationScenarios.length} 케이스</Badge>
            </div>

            <div className="w-full space-y-4">
                {integrationScenarios.map((scenario, index) => {
                    const isOpen = openIndex === index;
                    return (
                        <div
                            key={index}
                            className="border rounded-xl bg-card overflow-hidden shadow-sm"
                        >
                            <button
                                className="w-full hover:bg-muted/50 transition-colors py-4 px-6 flex items-center justify-between group"
                                onClick={() => setOpenIndex(isOpen ? null : index)}
                            >
                                <div className="flex items-center gap-4 text-left">
                                    <Badge className={getMethodColor(scenario.http_method)}>
                                        {scenario.http_method}
                                    </Badge>
                                    <div className="space-y-1">
                                        <div className="font-mono text-sm font-bold">{scenario.endpoint}</div>
                                        <div className="text-xs text-muted-foreground line-clamp-1">
                                            원인 메서드: {scenario.trigger_methods.map(m => `${getMethodName(m)}()`).join(", ")}
                                        </div>
                                    </div>
                                </div>
                                {isOpen ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                            </button>

                            {isOpen && (
                                <div className="px-6 pt-2 pb-6 space-y-6 border-t bg-muted/5">

                                    {/* 시나리오 설명 */}
                                    <section className="space-y-2">
                                        <div className="flex items-center gap-2 text-sm font-bold text-primary">
                                            <CheckCircle2 className="h-4 w-4" />
                                            <span>시나리오 및 기대 결과</span>
                                        </div>
                                        <div className="bg-card p-4 rounded-lg border space-y-3 shadow-sm">
                                            <div className="space-y-4">
                                                <div>
                                                    <span className="font-bold text-blue-600 block mb-1">의도:</span>
                                                    <div className="text-sm leading-relaxed prose prose-sm dark:prose-invert max-w-none">
                                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{scenario.result.scenario}</ReactMarkdown>
                                                    </div>
                                                </div>
                                                <div className="border-t pt-3">
                                                    <span className="font-bold text-green-600 block mb-1">기대 결과:</span>
                                                    <div className="text-sm leading-relaxed prose prose-sm dark:prose-invert max-w-none scenario-table">
                                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{scenario.result.expected_result}</ReactMarkdown>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </section>


                                    {/* Request & Response 페이로드 (상하 분할) */}
                                    <section className="space-y-3">
                                        <div className="flex items-center gap-2 text-sm font-bold text-primary">
                                            <Code2 className="h-4 w-4" />
                                            <span>Request & Response</span>
                                        </div>

                                        {/* Request */}
                                        <div className="space-y-2">
                                            <div className="flex items-center justify-between px-3 py-1.5 bg-blue-500/10 border-l-4 border-blue-500 rounded">
                                                <span className="text-sm font-semibold text-blue-600">Request</span>
                                            </div>

                                            {/* Request Headers */}
                                            {scenario.result.request.headers && (
                                                <div className="bg-muted/50 p-3 rounded-lg border border-dashed">
                                                    <div className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Headers</div>
                                                    <pre className="text-xs font-mono whitespace-pre-wrap">{scenario.result.request.headers}</pre>
                                                </div>
                                            )}

                                            <div className="rounded-lg overflow-hidden border shadow-sm">
                                                <SyntaxHighlighter
                                                    language="json"
                                                    style={vscDarkPlus}
                                                    customStyle={{ margin: 0, padding: '16px', fontSize: '12px' }}
                                                >
                                                    {JSON.stringify(scenario.result.request.payload, null, 2)}
                                                </SyntaxHighlighter>
                                            </div>
                                        </div>

                                        {/* Response */}
                                        <div className="space-y-2">
                                            <div className="flex items-center justify-between px-3 py-1.5 bg-green-500/10 border-l-4 border-green-500 rounded">
                                                <span className="text-sm font-semibold text-green-600">Response</span>
                                            </div>

                                            {/* Response Headers */}
                                            {scenario.result.response.headers && (
                                                <div className="bg-muted/50 p-3 rounded-lg border border-dashed">
                                                    <div className="text-[10px] uppercase font-bold text-muted-foreground mb-1">Headers</div>
                                                    <pre className="text-xs font-mono whitespace-pre-wrap">{scenario.result.response.headers}</pre>
                                                </div>
                                            )}

                                            <div className="rounded-lg overflow-hidden border shadow-sm">
                                                <SyntaxHighlighter
                                                    language="json"
                                                    style={vscDarkPlus}
                                                    customStyle={{ margin: 0, padding: '16px', fontSize: '12px' }}
                                                >
                                                    {JSON.stringify(scenario.result.response.payload, null, 2)}
                                                </SyntaxHighlighter>
                                            </div>
                                        </div>
                                    </section>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function getMethodColor(method: string) {
    switch (method?.toUpperCase()) {
        case 'GET': return 'bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 border-blue-500/20';
        case 'POST': return 'bg-green-500/10 text-green-500 hover:bg-green-500/20 border-green-500/20';
        case 'PUT': return 'bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20 border-yellow-500/20';
        case 'DELETE': return 'bg-red-500/10 text-red-500 hover:bg-red-500/20 border-red-500/20';
        default: return 'bg-slate-500/10 text-slate-500';
    }
}
