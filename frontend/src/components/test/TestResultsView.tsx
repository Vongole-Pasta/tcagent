
"use client";

import React from 'react';
import { Button } from "@/components/ui/button";
import { Download, FileSpreadsheet } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export interface GeneratedScenario {
    test_case_id: string;
    test_case_name: string;
    step_no: number;
    description: string;
    pre_condition: string;
    procedure: string;
    expected_result: string;
    scenario_id: string;
    root_method_signature: string;
}

interface TestResultsViewProps {
    scenarios: GeneratedScenario[];
    strategySummary?: string | null;
    updateScenario: (index: number, field: keyof GeneratedScenario, value: string | number) => void;
    onDownload: () => void;
}

export function TestResultsView({ scenarios, strategySummary, updateScenario, onDownload }: TestResultsViewProps) {

    if (scenarios.length === 0 && !strategySummary) {
        return (
            <Card className="items-center justify-center flex flex-col p-10 border-dashed border-2 bg-slate-50/50 mt-8">
                <div className="flex flex-col items-center justify-center h-40 text-center space-y-4">
                    <FileSpreadsheet className="h-16 w-16 text-slate-200" />
                    <div className="space-y-2">
                        <h3 className="text-lg font-medium">검색 결과 없음</h3>
                        <p className="text-sm text-muted-foreground max-w-sm">
                            생성된 테스트 시나리오가 없습니다. "테스트 생성" 버튼을 눌러주세요.
                        </p>
                    </div>
                </div>
            </Card>
        );
    }

    const renderMarkdown = (text: string) => {
        if (!text) return null;
        return text.split('\n').map((line, idx) => {
            if (line.startsWith('### ')) {
                return <h3 key={idx} className="text-md font-semibold mt-4 mb-2 text-blue-700">{line.replace('### ', '')}</h3>;
            }
            if (line.startsWith('## ')) {
                return <h2 key={idx} className="text-lg font-bold mt-6 mb-3 border-b pb-1">{line.replace('## ', '')}</h2>;
            }
            if (line.startsWith('- ')) {
                const content = line.replace('- ', '');
                const parts = content.split(/(\*\*.*?\*\*)/g);
                return (
                    <li key={idx} className="ml-4 list-disc text-sm text-slate-700 my-1">
                        {parts.map((part, pIdx) => {
                            if (part.startsWith('**') && part.endsWith('**')) {
                                return <strong key={pIdx} className="font-semibold text-slate-900 bg-yellow-50 px-1 rounded">{part.slice(2, -2)}</strong>;
                            }
                            return part;
                        })}
                    </li>
                );
            }
            return <p key={idx} className="text-sm text-slate-600 my-1">{line}</p>;
        });
    };

    return (
        <div className="space-y-4 mt-8">
            <div className="flex justify-between items-center bg-white p-4 rounded-lg border shadow-sm">
                <div>
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                        ✨ 테스트 분석 결과
                    </h2>
                    <p className="text-sm text-muted-foreground">
                        {scenarios.length > 0
                            ? `생성된 시나리오 ${scenarios.length}건 및 전략 분석 결과입니다.`
                            : "전략 분석 결과입니다. 테스트 시나리오를 생성하려면 '테스트 생성'을 클릭하세요."}
                    </p>
                </div>
                {scenarios.length > 0 && (
                    <Button onClick={onDownload} variant="outline" className="gap-2 border-green-600 text-green-700 hover:bg-green-50">
                        <Download className="h-4 w-4" />
                        Excel 다운로드
                    </Button>
                )}
            </div>

            <Tabs defaultValue={strategySummary ? "strategy" : "vod"} className="w-full">
                <TabsList>
                    <TabsTrigger value="strategy">요약 (Summary)</TabsTrigger>
                    <TabsTrigger value="vod">VOD (Detailed)</TabsTrigger>
                    <TabsTrigger value="scenario">시나리오 (Scenario)</TabsTrigger>
                </TabsList>

                <TabsContent value="strategy" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>테스트 전략 리포트</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {strategySummary ? (
                                <div className="prose prose-sm max-w-none p-4 bg-slate-50 rounded-md border text-slate-700 leading-relaxed">
                                    {renderMarkdown(strategySummary)}
                                </div>
                            ) : (
                                <div className="text-center py-10 text-slate-400">
                                    전략 분석 결과가 없습니다. "전략 분석" 버튼을 눌러주세요.
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="vod" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>VOD 시트 미리보기</CardTitle>
                        </CardHeader>
                        <CardContent className="p-0">
                            <div className="border rounded-md overflow-hidden">
                                <Table>
                                    <TableHeader className="bg-slate-50">
                                        <TableRow>
                                            <TableHead className="w-[100px]">ID</TableHead>
                                            <TableHead className="w-[150px]">테스트 케이스 명</TableHead>
                                            <TableHead className="w-[60px]">단계</TableHead>
                                            <TableHead className="w-[250px]">설명</TableHead>
                                            <TableHead className="w-[200px]">사전 조건</TableHead>
                                            <TableHead className="w-[200px]">수행 절차</TableHead>
                                            <TableHead className="w-[200px]">기대 결과</TableHead>
                                            <TableHead className="w-[100px]">시나리오 ID</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {scenarios.map((scenario, idx) => (
                                            <TableRow key={idx}>
                                                <TableCell className="font-mono text-xs">{scenario.test_case_id}</TableCell>
                                                <TableCell>
                                                    <Input
                                                        value={scenario.test_case_name}
                                                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateScenario(idx, 'test_case_name', e.target.value)}
                                                        className="h-8 text-xs bg-transparent border-transparent hover:border-input focus:border-input"
                                                    />
                                                </TableCell>
                                                <TableCell className="text-center">{scenario.step_no}</TableCell>
                                                <TableCell>
                                                    <Textarea
                                                        value={scenario.description}
                                                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => updateScenario(idx, 'description', e.target.value)}
                                                        className="min-h-[60px] text-xs bg-transparent border-transparent hover:border-input focus:border-input resize-none"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Textarea
                                                        value={scenario.pre_condition}
                                                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => updateScenario(idx, 'pre_condition', e.target.value)}
                                                        className="min-h-[60px] text-xs bg-transparent border-transparent hover:border-input focus:border-input resize-none"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Textarea
                                                        value={scenario.procedure}
                                                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => updateScenario(idx, 'procedure', e.target.value)}
                                                        className="min-h-[60px] text-xs bg-transparent border-transparent hover:border-input focus:border-input resize-none"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Textarea
                                                        value={scenario.expected_result}
                                                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => updateScenario(idx, 'expected_result', e.target.value)}
                                                        className="min-h-[60px] text-xs bg-transparent border-transparent hover:border-input focus:border-input resize-none"
                                                    />
                                                </TableCell>
                                                <TableCell className="font-mono text-xs text-muted-foreground">{scenario.scenario_id}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="scenario" className="mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>시나리오 시트 미리보기</CardTitle>
                        </CardHeader>
                        <CardContent className="p-0">
                            <div className="border rounded-md">
                                <Table>
                                    <TableHeader className="bg-slate-50">
                                        <TableRow>
                                            <TableHead className="w-[120px]">시나리오 ID</TableHead>
                                            <TableHead className="w-[200px]">함수명 (진입점)</TableHead>
                                            <TableHead>설명</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {/* Deduplicate scenarios by scenario_id for this view */}
                                        {Array.from(new Set(scenarios.map(s => s.scenario_id))).map(sid => {
                                            const scenario = scenarios.find(s => s.scenario_id === sid);
                                            if (!scenario) return null;
                                            return (
                                                <TableRow key={sid}>
                                                    <TableCell className="font-mono">{scenario.scenario_id}</TableCell>
                                                    <TableCell className="font-mono text-xs text-blue-600">
                                                        {scenario.root_method_signature}
                                                    </TableCell>
                                                    <TableCell>{scenario.description}</TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
