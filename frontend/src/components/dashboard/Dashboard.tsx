"use client";

import React, { useState } from 'react';
import { useStore } from '@/store/useStore';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from '@/components/ui/button';
import { TestResultsView, GeneratedScenario } from '@/components/test/TestResultsView';
import { Activity, Box, Globe, MousePointerClick, Sparkles, Loader2 } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function Dashboard() {
    const {
        projectNodes,
        generatedScenarios,
        strategySummary,
        setGeneratedTestResults,
        updateScenario
    } = useStore();

    const totalMethods = projectNodes.length; // All nodes are methods, some have endpoints
    const totalEndpoints = projectNodes.filter(n => n.type === 'ENDPOINT').length;

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleGenerate = async () => {
        setLoading(true);
        setError(null);
        // Clear previous results in store? Optional, but good for UX to show loading state cleanly.
        // setGeneratedTestResults([], null);

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
            setGeneratedTestResults(data.scenarios || [], data.strategy_summary || null);
        } catch (err: any) {
            setError(err.message || "An error occurred");
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = async () => {
        try {
            // 동적 import로 xlsx 로드 (클라이언트 사이드에서만 필요)
            const XLSX = await import("xlsx");

            // 1. Workbook 생성
            const wb = XLSX.utils.book_new();

            // 2. Summary 시트 생성
            const cleanSummary = (strategySummary || "요약 정보 없음")
                .replace(/```markdown/g, "")
                .replace(/```/g, "")
                .trim();

            const summaryLines = cleanSummary.split('\n');
            const summaryData = [
                ["테스트 전략 요약"],
                ...summaryLines.map(line => [line])
            ];
            const wsSummary = XLSX.utils.aoa_to_sheet(summaryData);
            // 간단한 컬럼 너비 설정
            wsSummary['!cols'] = [{ wch: 100 }];
            XLSX.utils.book_append_sheet(wb, wsSummary, "Summary");

            // 3. VOD 시트 생성
            // 데이터 매핑
            const vodData = generatedScenarios.map(s => ({
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
            // 컬럼 너비 자동 조절 (간단하게)
            wsVod['!cols'] = [
                { wch: 15 }, { wch: 20 }, { wch: 8 }, { wch: 30 },
                { wch: 20 }, { wch: 30 }, { wch: 30 }, { wch: 25 }, { wch: 15 }
            ];
            XLSX.utils.book_append_sheet(wb, wsVod, "VOD");

            // 4. Scenario 시트 생성
            // 중복 제거된 시나리오 목록 (scenario_id 기준)
            const uniqueScenarios = Array.from(new Set(generatedScenarios.map(s => s.scenario_id)))
                .map(sid => {
                    const s = generatedScenarios.find(sc => sc.scenario_id === sid);
                    return {
                        "Scenario ID": s?.scenario_id,
                        "Func Name": s?.root_method_signature,
                        "Description": s?.description
                    };
                }).filter(s => s["Scenario ID"]); // 유효한 데이터만

            const wsScenario = XLSX.utils.json_to_sheet(uniqueScenarios);
            wsScenario['!cols'] = [{ wch: 15 }, { wch: 40 }, { wch: 50 }];
            XLSX.utils.book_append_sheet(wb, wsScenario, "시나리오");

            // 5. 파일 다운로드
            const filename = `integrated_tests_${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.xlsx`;
            XLSX.writeFile(wb, filename);

        } catch (err: any) {
            console.error("Excel export failed:", err);
            setError(err.message || "Excel export failed");
        }
    };

    return (
        <div className="p-8 h-full bg-slate-50 overflow-y-auto">
            <div className="max-w-5xl mx-auto space-y-8">

                {/* Header */}
                <div className="space-y-2">
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">Project Dashboard</h1>
                    <p className="text-slate-500">
                        Welcome to TcAgent. Here is a summary of the analyzed project.
                    </p>
                </div>

                {/* Stats Grid */}
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Total Methods</CardTitle>
                            <Box className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{totalMethods}</div>
                            <p className="text-xs text-muted-foreground">
                                Identified functions & constructors
                            </p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Endpoints</CardTitle>
                            <Globe className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{totalEndpoints}</div>
                            <p className="text-xs text-muted-foreground">
                                Rest API Entry Points
                            </p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Test Scenarios</CardTitle>
                            <Activity className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{generatedScenarios.length}</div>
                            <p className="text-xs text-muted-foreground">
                                Generated test cases
                            </p>
                        </CardContent>
                    </Card>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-between p-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-100 shadow-sm">
                    <div>
                        <h3 className="text-lg font-semibold text-blue-900">통합 테스트 생성</h3>
                        <p className="text-sm text-blue-700 mt-1">
                            현재 그래프 분석을 기반으로 포괄적인 통합 테스트 시나리오를 자동으로 생성합니다.
                        </p>
                    </div>
                    <Button
                        size="lg"
                        onClick={handleGenerate}
                        disabled={loading}
                        className="bg-blue-600 hover:bg-blue-700 shadow-md transition-all hover:scale-105"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                생성 중...
                            </>
                        ) : (
                            <>
                                <Sparkles className="mr-2 h-4 w-4" />
                                테스트 생성
                            </>
                        )}
                    </Button>
                </div>

                {/* Error Message */}
                {error && (
                    <div className="p-4 bg-red-50 text-red-600 rounded-md text-sm border border-red-200">
                        Error: {error}
                    </div>
                )}

                {/* Content Area: Guide or Results */}
                {generatedScenarios.length > 0 || strategySummary ? (
                    <TestResultsView
                        scenarios={generatedScenarios}
                        strategySummary={strategySummary}
                        updateScenario={updateScenario}
                        onDownload={handleDownload}
                    />
                ) : (
                    /* Guide / Empty State Helper */
                    <Card className="items-center justify-center flex flex-col p-10 border-dashed border-2 bg-slate-50/50">
                        <div className="bg-blue-100 p-4 rounded-full mb-4">
                            <MousePointerClick className="h-8 w-8 text-blue-600" />
                        </div>
                        <h3 className="text-xl font-semibold mb-2">사용 방법</h3>
                        <p className="text-muted-foreground text-center max-w-md">
                            왼쪽 사이드바에서 <strong>Method</strong> 또는 <strong>Endpoint</strong>를 선택하여 호출 그래프와 의존성을 시각화하세요.
                            <br />
                            또는 위 <strong>"테스트 생성"</strong> 버튼을 눌러 변경된 코드에 대한 테스트 시나리오를 확인하세요.
                        </p>
                    </Card>
                )}

            </div>
        </div>
    );
}
