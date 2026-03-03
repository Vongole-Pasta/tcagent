"use client";

import React from 'react';
import { useStore } from '@/store/useStore';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from '@/components/ui/button';
import { Activity, Box, Globe, MousePointerClick, Share2, TestTube, Lightbulb, ArrowRight } from 'lucide-react';

export function Dashboard() {
    const { 
        projectNodes, 
        setViewMode,
        selectedProject
    } = useStore();

    const totalMethods = projectNodes.length;
    const totalEndpoints = projectNodes.filter(n => n.type === 'ENDPOINT').length;
    const modifiedMethods = projectNodes.filter(n => n.status === 'MODIFIED').length;

    return (
        <div className="p-8 h-full bg-slate-50 overflow-y-auto">
            <div className="max-w-5xl mx-auto space-y-8 pb-20">

                {/* Header */}
                <div className="space-y-2">
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900">Project Overview</h1>
                    <p className="text-slate-500">
                        {selectedProject ? `Project: ${selectedProject}` : '분석된 프로젝트의 현황과 사용 가이드를 확인하세요.'}
                    </p>
                </div>

                {/* Stats Grid */}
                <div className="grid gap-4 md:grid-cols-3">
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Total Methods</CardTitle>
                            <Box className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{totalMethods}</div>
                            <p className="text-xs text-muted-foreground">식별된 전체 함수 및 메서드</p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Endpoints</CardTitle>
                            <Globe className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{totalEndpoints}</div>
                            <p className="text-xs text-muted-foreground">API 진입점</p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium">Modifications</CardTitle>
                            <Activity className={`h-4 w-4 ${modifiedMethods > 0 ?'text-orange-500' : 'text-muted-foreground'}`} />
                        </CardHeader>
                        <CardContent>
                            <div className={`text-2xl font-bold ${modifiedMethods > 0 ? 'text-orange-600' : 'text-green-600'}`}>
                                {modifiedMethods > 0 ? `${modifiedMethods} Elements` : 'Stable'}
                            </div>
                            <p className="text-xs text-muted-foreground">변경 감지된 구성 요소</p>
                        </CardContent>
                    </Card>
                </div>

                {/* Getting Started / Quick Guide */}
                <div className="space-y-4">
                    <h2 className="text-xl font-semibold flex items-center gap-2">
                        <Lightbulb className="h-5 w-5 text-yellow-500" />
                        Quick Start Guide
                    </h2>
                    
                    <div className="grid gap-4 md:grid-cols-2">
                        <Card className="hover:border-primary/50 transition-colors cursor-pointer group" onClick={() => setViewMode('graph')}>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <Share2 className="h-5 w-5 text-blue-500" />
                                    모듈 간 관계 시각화
                                </CardTitle>
                                <CardDescription>
                                    사이드바에서 관심 있는 메서드를 클릭하여 Upstream/Downstream 호출 관계를 확인하세요.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="flex justify-end pt-0">
                                <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                            </CardContent>
                        </Card>

                        <Card className="hover:border-primary/50 transition-colors cursor-pointer group" onClick={() => setViewMode('results')}>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <TestTube className="h-5 w-5 text-emerald-500" />
                                    Happy Case 테스트 생성
                                </CardTitle>
                                <CardDescription>
                                    사이드바에서 하나 이상의 메서드를 체크하고 하단의 'Happy Case 생성' 버튼을 누르세요.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="flex justify-end pt-0">
                                <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                            </CardContent>
                        </Card>
                    </div>
                </div>

                {/* Status Help */}
                <Card className="bg-white/50 border-dashed">
                    <CardHeader>
                        <CardTitle className="text-lg">분석 가이드</CardTitle>
                    </CardHeader>
                    <CardContent className="grid gap-6 md:grid-cols-3">
                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <div className="h-2 w-2 rounded-full bg-green-500" />
                                <span className="font-medium text-sm">NEW</span>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                                새롭게 구현된 메서드입니다. 전체 호출 그래프에서 해당 기능이 어떻게 통합되었는지 확인이 필요합니다.
                            </p>
                        </div>
                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <div className="h-2 w-2 rounded-full bg-blue-500" />
                                <span className="font-medium text-sm">MODIFIED</span>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                                기존 로직이 수정된 부분입니다. 사이드바에서 선택하여 영향도(Impact Analysis)를 시각화하고 Test Case를 생성하세요.
                            </p>
                        </div>
                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <div className="h-2 w-2 rounded-full bg-red-500" />
                                <span className="font-medium text-sm">DELETED</span>
                            </div>
                            <p className="text-xs text-muted-foreground leading-relaxed">
                                삭제된 로직입니다. 참조하고 있던 다른 모듈들(Upstream)에 오류가 발생하지 않는지 확인하십시오.
                            </p>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
