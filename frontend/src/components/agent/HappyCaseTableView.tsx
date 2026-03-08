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
    if (!data) return String(data);

    // 이미 객체면 바로 변환
    if (typeof data !== 'string') {
        return JSON.stringify(data, null, 2);
    }

    try {
        let parsed = data;
        let depth = 0;

        // 문자열인 경우 최대 3번까지 재귀적으로 껍데기를 벗겨냄
        while (typeof parsed === 'string' && depth < 3) {
            let cleaned = parsed.trim();

            // 1. 최외곽 따옴표 무력화
            if ((cleaned.startsWith('"') && cleaned.endsWith('"')) || (cleaned.startsWith("'") && cleaned.endsWith("'"))) {
                if (cleaned.length > 1) {
                    cleaned = cleaned.substring(1, cleaned.length - 1);
                }
            }

            // 2. 백엔드/LLM 통신 중 붙은 모든 더러운 이스케이프 무력화
            cleaned = cleaned.replace(/\\\\"/g, '"');   // \\" -> "
            cleaned = cleaned.replace(/\\\\/g, '\\');   // \\ -> \
            cleaned = cleaned.replace(/\\"/g, '"');     // \" -> "
            cleaned = cleaned.replace(/\\n/g, '\n');    // \n -> 줄바꿈
            cleaned = cleaned.replace(/\\t/g, '\t');    // \t -> 탭

            try {
                // 3. 정석적인 JSON 파싱 시도
                parsed = JSON.parse(cleaned);
            } catch (e1) {
                try {
                    // 4. (최후의 보루) 정석 파싱 실패 시, JavaScript 파싱 엔진 차용
                    // 이중/삼중 이스케이프로 문법이 미세하게 파괴된 경우 
                    // JS 객체 리터럴로 억지로 읽어들여 복구하는 무적 로직
                    parsed = new Function('return ' + cleaned)();
                } catch (e2) {
                    // 어떻게 해도 안 풀리면 치환만 된 문자열을 그대로 반환 (다음 depth 진행 방지)
                    parsed = cleaned;
                    break;
                }
            }
            depth++;
        }

        // 마침내 건져낸 순수 객체를 예쁘게 리턴
        return typeof parsed === 'object' ? JSON.stringify(parsed, null, 2) : parsed;

    } catch (finalError) {
        console.error("Critical JSON formatting error:", finalError);
        // 서버에서 던진 원본 그대로 어쩔 수 없이 출력
        return String(data);
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
