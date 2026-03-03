"use client";

import React from 'react';
import { useStore } from '@/store/useStore';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, FlaskConical } from "lucide-react";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, prism } from 'react-syntax-highlighter/dist/esm/styles/prism';

export function HappyCaseTableView() {
    const { happyCaseScenarios, projectNodes } = useStore();

    const getMethodName = (methodId: string) => {
        const node = projectNodes.find(n => n.id === methodId);
        return node ? node.name : methodId;
    };

    if (happyCaseScenarios.length === 0) {
        return null;
    }

    return (
        <Card className="shadow-md border-primary/20 overflow-hidden py-0 gap-0">
            <CardHeader className="bg-gradient-to-r from-primary/10 via-primary/5 to-background p-6 border-b">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-primary/10 rounded-lg">
                            <FlaskConical className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                            <CardTitle className="text-xl font-bold tracking-tight">Happy Case 테스트 시나리오</CardTitle>
                            <p className="text-xs text-muted-foreground mt-1">일괄 생성된 검증용 테스트 데이터셋</p>
                        </div>
                    </div>
                    <Badge variant="secondary" className="px-3 py-1 font-mono">
                        {happyCaseScenarios.length} Cases
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="p-0">
                <Table className="table-fixed w-full">
                    <TableHeader className="bg-muted/50">
                        <TableRow>
                            <TableHead className="w-[80px] font-bold text-center">ID</TableHead>
                            <TableHead className="w-[150px] font-bold text-center">Target 메서드</TableHead>
                            <TableHead className="w-auto font-bold text-center">테스트 케이스</TableHead>
                            <TableHead className="w-[30%] font-bold text-center">입력 데이터</TableHead>
                            <TableHead className="w-[30%] font-bold text-center">예상 결과</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {happyCaseScenarios.map((scenario, index) => (
                            <TableRow key={index} className="hover:bg-muted/30 transition-colors">
                                <TableCell className="font-mono text-xs font-bold text-center align-top pt-4">
                                    <Badge variant="secondary">{scenario.test_case_id}</Badge>
                                </TableCell>
                                <TableCell className="align-top pt-4 text-center">
                                    <div className="flex flex-col gap-1 items-center">
                                        {scenario.trigger_methods?.slice(0, 3).map((id, i) => (
                                            <Badge key={i} variant="outline" className="bg-blue-50/50 text-blue-700 border-blue-200 text-[10px] py-0 px-1.5 font-medium max-w-[130px] truncate">
                                                {getMethodName(id)}
                                            </Badge>
                                        ))}
                                        {scenario.trigger_methods && scenario.trigger_methods.length > 3 && (
                                            <span className="text-[10px] text-muted-foreground">외 {scenario.trigger_methods.length - 3}개</span>
                                        )}
                                        {(!scenario.trigger_methods || scenario.trigger_methods.length === 0) && (
                                            <span className="text-[10px] text-muted-foreground">-</span>
                                        )}
                                    </div>
                                </TableCell>
                                <TableCell className="align-top pt-4 pb-4">
                                    <div className="space-y-2 min-w-0">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <Badge variant="outline" className={getMethodColor(scenario.http_method)}>
                                                {scenario.http_method}
                                            </Badge>
                                            <span className="text-[11px] font-mono text-muted-foreground break-all">
                                                {scenario.endpoint}
                                            </span>
                                        </div>
                                        <p className="text-xs font-medium leading-relaxed break-words whitespace-normal">
                                            {scenario.test_case}
                                        </p>
                                    </div>
                                </TableCell>
                                <TableCell className="align-top p-3 text-center">
                                    <div className="rounded-md overflow-hidden border">
                                        <SyntaxHighlighter
                                            language="json"
                                            style={vscDarkPlus}
                                            customStyle={{
                                                margin: 0,
                                                padding: '12px',
                                                fontSize: '12px',
                                                fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                                                textAlign: 'left'
                                            }}
                                            codeTagProps={{
                                                style: {
                                                    fontSize: '12px',
                                                    fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                                                }
                                            }}
                                            wrapLongLines={true}
                                        >
                                            {formatJson(scenario.input_data)}
                                        </SyntaxHighlighter>
                                    </div>
                                </TableCell>
                                <TableCell className="align-top p-3 text-center">
                                    <div className="rounded-md overflow-hidden border">
                                        <SyntaxHighlighter
                                            language="json"
                                            style={prism}
                                            customStyle={{
                                                margin: 0,
                                                padding: '12px',
                                                fontSize: '12px',
                                                fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                                                backgroundColor: '#f8fafc',
                                                textAlign: 'left'
                                            }}
                                            codeTagProps={{
                                                style: {
                                                    fontSize: '12px',
                                                    fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                                                }
                                            }}
                                            wrapLongLines={true}
                                        >
                                            {formatJson(scenario.expected_result)}
                                        </SyntaxHighlighter>
                                    </div>
                                    <div className="mt-2 flex items-center justify-center gap-1 text-[10px] text-green-600 font-bold uppercase">
                                        <CheckCircle2 className="h-3 w-3" />
                                        <span>200 OK Expected</span>
                                    </div>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    );
}

function formatJson(data: any) {
    try {
        const obj = typeof data === 'string' ? JSON.parse(data) : data;
        return JSON.stringify(obj, null, 2);
    } catch (e) {
        return typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    }
}

function getMethodColor(method: string) {
    switch (method?.toUpperCase()) {
        case 'GET': return 'text-blue-600 border-blue-200 bg-blue-50';
        case 'POST': return 'text-green-600 border-green-200 bg-green-50';
        case 'PUT': return 'text-yellow-600 border-yellow-200 bg-yellow-50';
        case 'DELETE': return 'text-red-600 border-red-200 bg-red-50';
        default: return 'text-slate-600';
    }
}
