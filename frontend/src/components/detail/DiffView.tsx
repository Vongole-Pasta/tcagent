"use client";

import React from 'react';
import ReactDiffViewer, { DiffMethod } from 'react-diff-viewer-continued';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface DiffViewProps {
    oldCode: string;
    newCode: string;
}

/**
 * [소스 코드 Diff 뷰어]
 * react-diff-viewer-continued를 사용하여 이전 코드와 현재 코드의 차이를 시각적으로 보여줍니다.
 * 다크 모드 스타일이 적용되어 있으며, 단어 단위(WORDS) 비교를 수행합니다.
 * SyntaxHighlighter를 통합하여 Java 구문 강조를 제공합니다.
 */
export function DiffView({ oldCode, newCode }: DiffViewProps) {
    // Syntax highlighting wrapper for diff lines
    const syntaxHighlight = (str: string) => {
        if (!str) return <></>;
        return (
            <SyntaxHighlighter
                language="java"
                style={vscDarkPlus}
                customStyle={{ display: 'inline', padding: 0, background: 'transparent' }}
                codeTagProps={{ style: { background: 'transparent' } }}
            >
                {str}
            </SyntaxHighlighter>
        );
    };

    return (
        <div className="diff-viewer-container bg-[#1e1e1e] rounded-md overflow-hidden border border-border">
            <ReactDiffViewer
                oldValue={oldCode}
                newValue={newCode}
                splitView={true}
                compareMethod={DiffMethod.WORDS}
                useDarkTheme={true}
                leftTitle="변경 전 (Before)"
                rightTitle="변경 후 (After)"
                renderContent={syntaxHighlight}
                showDiffOnly={false}
                styles={{
                    variables: {
                        dark: {
                            diffViewerBackground: '#1e1e1e',
                            diffViewerColor: '#d4d4d4',
                            addedBackground: '#044219',
                            addedColor: '#acf2bd',
                            removedBackground: '#632929',
                            removedColor: '#ffd8d8',
                            addedGutterBackground: '#044219',
                            removedGutterBackground: '#632929',
                            wordAddedBackground: '#128a36',
                            wordRemovedBackground: '#9e2424',
                            gutterColor: '#858585',
                            codeFoldGutterBackground: '#212121',
                            codeFoldBackground: '#262626',
                            emptyLineBackground: '#1e1e1e',
                        }
                    },
                    contentText: {
                        fontSize: '13px',
                        lineHeight: '1.5',
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                    },
                    lineNumber: {
                        fontSize: '11px',
                    },
                    titleBlock: {
                        background: '#2d2d2d',
                        color: '#999',
                        padding: '8px 12px',
                        fontSize: '12px',
                        fontWeight: '600',
                        borderBottom: '1px solid #3e3e3e'
                    }
                }}
            />
        </div>
    );
}
