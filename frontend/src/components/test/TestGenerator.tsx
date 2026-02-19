
"use client";

import React, { useState } from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Sparkles, Download, FileSpreadsheet, Loader2 } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface GeneratedScenario {
    test_case_id: string;
    test_case_name: string;
    step_no: number;
    description: string;
    pre_condition: string;
    procedure: string;
    expected_result: string;
    scenario_id: string;
    root_method_signature?: string;
    api_endpoint?: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function TestGenerator({ trigger }: { trigger?: React.ReactNode }) {
    // Original State
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [scenarios, setScenarios] = useState<GeneratedScenario[]>([]);
    const [error, setError] = useState<string | null>(null);

    // Strategy State
    const [strategySummary, setStrategySummary] = useState<string | null>(null);
    const [analyzing, setAnalyzing] = useState(false);

    // Popup State
    const [showSuccessPopup, setShowSuccessPopup] = useState(false);

    const handleGenerate = async () => {
        setLoading(true);
        setError(null);
        setScenarios([]);

        try {
            const response = await fetch(`${API_BASE_URL}/api/tests/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_id: 'default' })
            });

            if (!response.ok) {
                throw new Error('Failed to generate tests');
            }

            const data = await response.json();
            setScenarios(data.scenarios || []);
        } catch (err: any) {
            setError(err.message || "An error occurred");
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = async () => {
        try {
            // 동적 import로 xlsx 로드
            const XLSX = await import("xlsx");

            // 1. Workbook 생성
            const wb = XLSX.utils.book_new();

            // 2. Summary 시트 생성 (Optional)
            if (strategySummary) {
                const cleanSummary = strategySummary
                    .replace(/```markdown/g, "")
                    .replace(/```/g, "")
                    .trim();

                const summaryLines = cleanSummary.split('\n');
                const summaryData = [
                    ["테스트 전략 요약"],
                    ...summaryLines.map(line => [line])
                ];
                const wsSummary = XLSX.utils.aoa_to_sheet(summaryData);
                wsSummary['!cols'] = [{ wch: 100 }];
                XLSX.utils.book_append_sheet(wb, wsSummary, "Summary");
            }

            // 3. VOD 시트 생성
            const vodData = scenarios.map(s => ({
                "Test Case ID": s.test_case_id,
                "Test Case Name": s.test_case_name,
                "Step No": s.step_no,
                "Description": s.description,
                "Pre-condition": s.pre_condition,
                "Procedure": s.procedure,
                "Expected Result": s.expected_result,
                "API Endpoint": s.api_endpoint || s.root_method_signature || "",
                "Scenario ID": s.scenario_id
            }));
            const wsVod = XLSX.utils.json_to_sheet(vodData);
            wsVod['!cols'] = [
                { wch: 15 }, { wch: 20 }, { wch: 8 }, { wch: 30 },
                { wch: 20 }, { wch: 30 }, { wch: 30 }, { wch: 25 }, { wch: 15 }
            ];
            XLSX.utils.book_append_sheet(wb, wsVod, "VOD");

            // 4. Scenario 시트 생성
            const uniqueScenarios = Array.from(new Set(scenarios.map(s => s.scenario_id)))
                .map(sid => {
                    const s = scenarios.find(sc => sc.scenario_id === sid);
                    return {
                        "Scenario ID": s?.scenario_id,
                        "Func Name": s?.root_method_signature,
                        "Description": s?.description
                    };
                }).filter(s => s["Scenario ID"]);

            const wsScenario = XLSX.utils.json_to_sheet(uniqueScenarios);
            wsScenario['!cols'] = [{ wch: 15 }, { wch: 40 }, { wch: 50 }];
            XLSX.utils.book_append_sheet(wb, wsScenario, "시나리오");

            // 5. 파일 다운로드
            const filename = `integrated_tests_${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.xlsx`;
            XLSX.writeFile(wb, filename);

            setOpen(false); // Close dialog on success
        } catch (err: any) {
            console.error("Excel export failed:", err);
            setError(err.message || "Excel export failed");
        }
    };

    const updateScenario = (index: number, field: keyof GeneratedScenario, value: string | number) => {
        const newScenarios = [...scenarios];
        newScenarios[index] = { ...newScenarios[index], [field]: value };
        setScenarios(newScenarios);
    };

    const handleAnalyzeStrategy = async () => {
        setAnalyzing(true);
        setError(null);
        setStrategySummary(null);
        setShowSuccessPopup(false);

        try {
            const response = await fetch(`${API_BASE_URL}/api/strategy/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_id: 'default' })
            });

            if (!response.ok) {
                throw new Error('Failed to analyze strategy');
            }

            const data = await response.json();
            setStrategySummary(data.strategy_summary);
            setShowSuccessPopup(true); // Show popup on success
        } catch (err: any) {
            setError(err.message || "An error occurred");
        } finally {
            setAnalyzing(false);
        }
    };

    // Simple Markdown Renderer (Bold & Headers)
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
                // Bold processing: **text**
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
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                {trigger || (
                    <Button size="lg" className="bg-blue-600 hover:bg-blue-700 shadow-md">
                        <Sparkles className="mr-2 h-4 w-4" />
                        Generate Tests
                    </Button>
                )}
            </DialogTrigger>
            <DialogContent className="max-w-6xl max-h-[90vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Sparkles className="h-5 w-5 text-blue-600" />
                        Integrated Test Generator & Strategy
                    </DialogTitle>
                </DialogHeader>

                <div className="flex-1 overflow-auto p-4 space-y-6">
                    {/* Strategy Section */}
                    <div className="bg-slate-50 p-4 rounded-lg border">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="font-semibold text-slate-800 flex items-center gap-2">
                                <FileSpreadsheet className="h-4 w-4" />
                                1. 변경점 분석 및 테스트 전략 (Strategy)
                            </h3>
                            <Button
                                onClick={handleAnalyzeStrategy}
                                disabled={analyzing}
                                variant="outline"
                                size="sm"
                                className="border-blue-200 hover:bg-blue-50 text-blue-700"
                            >
                                {analyzing ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : "🔍 "}
                                전략 분석 실행
                            </Button>
                        </div>

                        {analyzing && (
                            <div className="py-8 text-center text-sm text-muted-foreground animate-pulse">
                                변경된 코드와 영향 범위를 분석하고 있습니다...
                            </div>
                        )}

                        {strategySummary && (
                            <div className="bg-white p-4 rounded border shadow-sm prose prose-sm max-w-none">
                                {renderMarkdown(strategySummary)}
                            </div>
                        )}
                    </div>

                    {/* Generation Section */}
                    <div className="bg-white p-4 rounded-lg border">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="font-semibold text-slate-800 flex items-center gap-2">
                                <Sparkles className="h-4 w-4" />
                                2. 상세 시나리오 생성 (Details)
                            </h3>
                        </div>

                        {loading ? (
                            <div className="flex flex-col items-center justify-center h-40 gap-4">
                                <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
                                <p className="text-muted-foreground animate-pulse">Call Graph 분석 및 시나리오 생성 중...</p>
                            </div>
                        ) : scenarios.length > 0 ? (
                            <div className="space-y-4">
                                <div className="flex justify-between items-center">
                                    <p className="text-sm text-green-600 font-medium">✨ 총 {scenarios.length}개의 시나리오가 생성되었습니다.</p>
                                    <Button onClick={handleDownload} variant="outline" className="gap-2 border-green-600 text-green-700 hover:bg-green-50">
                                        <Download className="h-4 w-4" />
                                        Excel 다운로드
                                    </Button>
                                </div>
                                <div className="border rounded-md max-h-[400px] overflow-auto">
                                    <Table>
                                        <TableHeader className="sticky top-0 bg-white z-10 shadow-sm">
                                            <TableRow>
                                                <TableHead className="w-[120px]">ID</TableHead>
                                                <TableHead className="w-[150px]">Case Name</TableHead>
                                                <TableHead className="w-[200px]">Procedure</TableHead>
                                                <TableHead className="w-[200px]">Expected Result</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {scenarios.map((scenario, idx) => (
                                                <TableRow key={idx}>
                                                    <TableCell className="font-mono text-xs">{scenario.test_case_id}</TableCell>
                                                    <TableCell className="text-xs">{scenario.test_case_name}</TableCell>
                                                    <TableCell>
                                                        <Textarea
                                                            value={scenario.procedure}
                                                            readOnly
                                                            className="min-h-[40px] text-xs bg-slate-50 resize-none font-mono"
                                                        />
                                                    </TableCell>
                                                    <TableCell>
                                                        <Textarea
                                                            value={scenario.expected_result}
                                                            readOnly
                                                            className="min-h-[40px] text-xs bg-slate-50 resize-none font-mono"
                                                        />
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </div>
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center py-8 text-center space-y-4 bg-slate-50/50 rounded-lg border-2 border-dashed">
                                <p className="text-sm text-muted-foreground">
                                    위의 전략 분석을 확인한 후, 상세 시나리오를 생성하세요.
                                </p>
                                <Button onClick={handleGenerate} size="lg" disabled={loading} className="bg-blue-600 hover:bg-blue-700">
                                    시나리오 생성 시작
                                </Button>
                            </div>
                        )}
                    </div>

                    {error && (
                        <div className="p-4 bg-red-50 text-red-600 rounded-md text-sm border border-red-200">
                            Error: {error}
                        </div>
                    )}
                </div>

                {/* Analysis Complete Popup */}
                {showSuccessPopup && (
                    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-[1px] animate-in fade-in duration-200">
                        <div className="bg-white p-6 rounded-lg shadow-xl border border-blue-100 max-w-sm w-full text-center space-y-4 animate-in zoom-in-95 duration-200">
                            <div className="mx-auto bg-blue-100 w-12 h-12 rounded-full flex items-center justify-center">
                                <Sparkles className="h-6 w-6 text-blue-600" />
                            </div>
                            <div className="space-y-1">
                                <h3 className="text-lg font-semibold text-slate-900">전략 분석 완료!</h3>
                                <p className="text-sm text-slate-500">
                                    테스트 대상과 영향도가 분석되었습니다.<br />
                                    결과를 확인하고 시나리오를 생성하세요.
                                </p>
                            </div>
                            <Button
                                onClick={() => setShowSuccessPopup(false)}
                                className="w-full bg-blue-600 hover:bg-blue-700"
                            >
                                결과 확인하기
                            </Button>
                        </div>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );

}
