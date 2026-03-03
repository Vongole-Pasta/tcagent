"use client";

import React from 'react';
import { Loader2 } from 'lucide-react';

export function LoadingProgress() {
    return (
        <div className="flex flex-col items-center justify-center p-24 space-y-6 animate-in fade-in duration-500">
            <div className="relative">
                {/* 배경 광원 효과 */}
                <div className="absolute inset-0 bg-primary/20 rounded-full blur-3xl animate-pulse"></div>
                
                {/* 메인 로딩 아이콘 */}
                <div className="relative bg-background border-2 border-primary/10 p-8 rounded-3xl shadow-2xl">
                    <Loader2 className="h-14 w-14 text-primary animate-spin" />
                </div>
            </div>

            <div className="text-center space-y-2">
                <h3 className="text-xl font-bold tracking-tight text-foreground animate-pulse">
                    Happy Case 생성 중...
                </h3>
                <p className="text-sm text-muted-foreground max-w-[280px]">
                    AI 에이전트가 완벽한 테스트 시나리오를 설계하고 있습니다. 잠시만 기다려 주세요.
                </p>
            </div>

            {/* 하단 점진적 로딩 바 (단순 대기용) */}
            <div className="w-48 h-1 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-primary/40 animate-progress-loop"></div>
            </div>
        </div>
    );
}
