"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { GraphView } from "@/components/graph/GraphView";
import { DetailPanel } from "@/components/detail/DetailPanel";
import { Dashboard } from "@/components/dashboard/Dashboard";
import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { 
  HomeIcon, 
  LayoutDashboard, 
  Share2, 
  TestTube, 
  Activity, 
  User, 
  Lock, 
  Mail, 
  LogOut, 
  KeyRound, 
  ChevronDown,
  Loader2,
  CheckCircle2,
  AlertTriangle
} from "lucide-react";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { SuccessDialog } from "@/components/ui/success-dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { HappyCaseTableView } from "@/components/agent/HappyCaseTableView";
import { LoadingProgress } from "@/components/agent/LoadingProgress";
import { IntegrationScenarioView } from "@/components/agent/IntegrationScenarioView";

export default function Home() {
  const {
    selectedNodeId,
    clearSelection,
    isLoading,
    viewMode,
    setViewMode,
    happyCaseScenarios,
    integrationScenarios,
    isAgentRunning,
    
    // Auth State & Actions
    user,
    isAuthenticated,
    authError,
    login,
    signup,
    logout,
    checkAuth,
    clearAuthError
  } = useStore();

  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const [authView, setAuthView] = useState<'login' | 'signup'>('login');
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  // Form states
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  
  // Custom message modal after registration
  const [signupSuccessMessage, setSignupSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    checkAuth().finally(() => {
      setIsCheckingAuth(false);
    });
  }, [checkAuth]);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    const success = await login(email, password);
    if (success) {
      setEmail('');
      setPassword('');
    }
  };

  const handleSignupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !password) return;
    const success = await signup(name, email, password);
    if (success) {
      setName('');
      setEmail('');
      setPassword('');
      setSignupSuccessMessage("회원가입 요청이 성공적으로 완료되었습니다.\n관리자의 승인(approved) 처리 후 로그인이 가능합니다.");
      setAuthView('login');
    }
  };

  // Auth checking indicator
  if (isCheckingAuth) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-slate-50 dark:bg-zinc-950">
        <Loader2 className="h-10 w-10 animate-spin text-indigo-600 mb-2" />
        <p className="text-sm text-muted-foreground font-medium">인증 정보를 확인하는 중입니다...</p>
      </div>
    );
  }

  // LOGIN & SIGNUP SCREEN
  if (!isAuthenticated) {
    return (
      <main className="h-screen w-screen flex items-center justify-center bg-gradient-to-br from-slate-100 via-indigo-50/30 to-violet-100/50 dark:from-zinc-950 dark:via-indigo-950/20 dark:to-violet-950/30 p-4 relative overflow-hidden">
        {/* Soft glowing mesh circles in background */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl -z-10" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl -z-10" />
        
        {signupSuccessMessage && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <Card className="max-w-md w-full p-6 text-center shadow-2xl border-border bg-white dark:bg-zinc-900 animate-in zoom-in-95 duration-200">
              <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-4" />
              <h3 className="text-lg font-bold mb-2">가입 완료 (승인 대기)</h3>
              <p className="text-sm text-muted-foreground whitespace-pre-line mb-6 leading-relaxed">
                {signupSuccessMessage}
              </p>
              <Button className="w-full" onClick={() => setSignupSuccessMessage(null)}>
                확인
              </Button>
            </Card>
          </div>
        )}

        <div className="w-full max-w-md">
          {/* Card Container */}
          <Card className="w-full p-8 border border-white/20 dark:border-zinc-800/50 bg-white/75 dark:bg-zinc-900/80 backdrop-blur-lg shadow-2xl rounded-2xl transition-all duration-300">
            {authView === 'login' ? (
              // LOGIN FORM
              <form onSubmit={handleLoginSubmit} className="space-y-6">
                <div className="text-center space-y-1">
                  <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-violet-600 to-indigo-600 bg-clip-text text-transparent">
                    TC AGENT
                  </h1>
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
                    Java Code Analysis System
                  </p>
                </div>

                {authError && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs rounded-lg flex items-start gap-2 animate-in shake duration-300">
                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                    <span>{authError}</span>
                  </div>
                )}

                <div className="space-y-4">
                  {/* Email Input */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-zinc-600 dark:text-zinc-400">ID (Email)</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-3 h-4.5 w-4.5 text-muted-foreground" />
                      <Input
                        type="email"
                        placeholder="이메일을 입력해 주세요"
                        className="pl-10 h-11 bg-zinc-50/50 dark:bg-zinc-950/30 border-zinc-200 dark:border-zinc-800"
                        value={email}
                        onChange={(e) => {
                          setEmail(e.target.value);
                          if (authError) clearAuthError();
                        }}
                        required
                      />
                    </div>
                  </div>

                  {/* Password Input */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-zinc-600 dark:text-zinc-400">PW (Password)</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-3 h-4.5 w-4.5 text-muted-foreground" />
                      <Input
                        type="password"
                        placeholder="비밀번호를 입력해 주세요"
                        className="pl-10 h-11 bg-zinc-50/50 dark:bg-zinc-950/30 border-zinc-200 dark:border-zinc-800"
                        value={password}
                        onChange={(e) => {
                          setPassword(e.target.value);
                          if (authError) clearAuthError();
                        }}
                        required
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-3 pt-2">
                  <Button 
                    type="submit" 
                    className="w-full h-11 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white font-semibold rounded-xl shadow-lg shadow-indigo-500/20"
                    disabled={isLoading}
                  >
                    {isLoading ? <Loader2 className="h-4.5 w-4.5 animate-spin" /> : "LOGIN"}
                  </Button>
                  <Button 
                    type="button" 
                    variant="outline"
                    className="w-full h-11 border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 font-semibold rounded-xl"
                    onClick={() => {
                      setAuthView('signup');
                      clearAuthError();
                    }}
                  >
                    SIGN IN
                  </Button>
                </div>
              </form>
            ) : (
              // SIGNUP FORM
              <form onSubmit={handleSignupSubmit} className="space-y-6">
                <div className="text-center space-y-1">
                  <h1 className="text-2xl font-extrabold tracking-tight text-zinc-800 dark:text-zinc-100">
                    회원 가입
                  </h1>
                  <p className="text-xs text-muted-foreground">
                    계정 정보를 기입해 주세요.
                  </p>
                </div>

                {authError && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs rounded-lg flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                    <span>{authError}</span>
                  </div>
                )}

                <div className="space-y-4">
                  {/* Name Input */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-zinc-600 dark:text-zinc-400">이름</label>
                    <div className="relative">
                      <User className="absolute left-3 top-3 h-4.5 w-4.5 text-muted-foreground" />
                      <Input
                        type="text"
                        placeholder="이름을 입력해 주세요"
                        className="pl-10 h-11 bg-zinc-50/50 dark:bg-zinc-950/30 border-zinc-200 dark:border-zinc-800"
                        value={name}
                        onChange={(e) => {
                          setName(e.target.value);
                          if (authError) clearAuthError();
                        }}
                        required
                      />
                    </div>
                  </div>

                  {/* Email Input */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-zinc-600 dark:text-zinc-400">이메일</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-3 h-4.5 w-4.5 text-muted-foreground" />
                      <Input
                        type="email"
                        placeholder="이메일을 입력해 주세요"
                        className="pl-10 h-11 bg-zinc-50/50 dark:bg-zinc-950/30 border-zinc-200 dark:border-zinc-800"
                        value={email}
                        onChange={(e) => {
                          setEmail(e.target.value);
                          if (authError) clearAuthError();
                        }}
                        required
                      />
                    </div>
                  </div>

                  {/* Password Input */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-zinc-600 dark:text-zinc-400">패스워드</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-3 h-4.5 w-4.5 text-muted-foreground" />
                      <Input
                        type="password"
                        placeholder="비밀번호를 설정해 주세요"
                        className="pl-10 h-11 bg-zinc-50/50 dark:bg-zinc-950/30 border-zinc-200 dark:border-zinc-800"
                        value={password}
                        onChange={(e) => {
                          setPassword(e.target.value);
                          if (authError) clearAuthError();
                        }}
                        required
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-3 pt-2">
                  <Button 
                    type="submit" 
                    className="w-full h-11 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white font-semibold rounded-xl shadow-lg shadow-indigo-500/20"
                    disabled={isLoading}
                  >
                    {isLoading ? <Loader2 className="h-4.5 w-4.5 animate-spin" /> : "REG"}
                  </Button>
                  <Button 
                    type="button" 
                    variant="ghost"
                    className="w-full h-11 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 text-sm font-semibold rounded-xl"
                    onClick={() => {
                      setAuthView('login');
                      clearAuthError();
                    }}
                  >
                    로그인 화면으로 돌아가기
                  </Button>
                </div>
              </form>
            )}
          </Card>
        </div>
      </main>
    );
  }

  // MAIN DASHBOARD SCREEN (AUTHENTICATED)
  return (
    <main className="h-screen w-screen overflow-hidden flex bg-background text-foreground relative">
      {isLoading && <LoadingOverlay />}
      <SuccessDialog />

      {/* Left Sidebar - Fixed Width */}
      <aside className="w-[300px] flex-shrink-0 border-r bg-muted/10 h-full overflow-hidden">
        <Sidebar />
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-full relative min-w-0">
        <Tabs
          value={viewMode}
          onValueChange={(v) => setViewMode(v as any)}
          className="flex-1 flex flex-col h-full"
        >
          <div className="h-14 border-b flex items-center px-4 bg-background shrink-0 justify-between">
            <TabsList className="bg-muted/50">
              <TabsTrigger value="dashboard" className="gap-2">
                <LayoutDashboard className="h-4 w-4" />
                Overview
              </TabsTrigger>
              <TabsTrigger value="graph" className="gap-2">
                <Share2 className="h-4 w-4" />
                Visualization
              </TabsTrigger>
              <TabsTrigger value="results" className="gap-2">
                <TestTube className="h-4 w-4" />
                Test Results
              </TabsTrigger>
            </TabsList>

            <div className="flex items-center gap-3">
              {viewMode === 'graph' && selectedNodeId && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-2 text-muted-foreground hover:text-foreground h-9"
                  onClick={clearSelection}
                >
                  <HomeIcon className="h-4 w-4" />
                  Reset Graph
                </Button>
              )}

              {/* User Profile Dropdown */}
              <div className="relative shrink-0">
                <Button 
                  variant="ghost" 
                  size="sm"
                  className="flex items-center gap-2 px-3 h-9 rounded-lg border border-border/50 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                  onClick={() => setIsProfileOpen(!isProfileOpen)}
                >
                  <div className="w-5.5 h-5.5 rounded-full bg-indigo-500 text-white flex items-center justify-center text-[10px] font-bold">
                    {user?.name?.[0] || 'U'}
                  </div>
                  <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 hidden sm:inline-block">
                    {user?.name}
                  </span>
                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
                {isProfileOpen && (
                  <>
                    {/* Backdrop */}
                    <div className="fixed inset-0 z-40" onClick={() => setIsProfileOpen(false)} />
                    {/* Dropdown Menu */}
                    <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-zinc-900 border border-border shadow-lg rounded-lg z-50 overflow-hidden py-1 animate-in fade-in slide-in-from-top-2 duration-200">
                      <div className="px-4 py-2 border-b border-border/50">
                        <p className="text-[10px] text-muted-foreground truncate">{user?.email}</p>
                      </div>
                      <button 
                        onClick={() => {
                          setIsProfileOpen(false);
                          alert("비밀번호 변경 모달 (준비중)");
                        }}
                        className="w-full text-left px-4 py-2.5 text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center gap-2 text-zinc-700 dark:text-zinc-300"
                      >
                        <KeyRound className="h-3.5 w-3.5" />
                        비밀번호 변경
                      </button>
                      <button 
                        onClick={() => {
                          setIsProfileOpen(false);
                          logout();
                        }}
                        className="w-full text-left px-4 py-2.5 text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800 flex items-center gap-2 text-red-500 font-medium"
                      >
                        <LogOut className="h-3.5 w-3.5" />
                        로그아웃
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          <TabsContent value="dashboard" className="flex-1 m-0 overflow-auto">
            <Dashboard />
          </TabsContent>

          <TabsContent value="graph" className="flex-1 m-0 overflow-hidden">
            {selectedNodeId ? (
              <ResizablePanelGroup orientation="vertical">
                <ResizablePanel defaultSize={65} minSize={30}>
                  <div className="flex flex-col h-full">
                    <div className="flex-1 min-h-0 relative">
                      <GraphView />
                    </div>
                  </div>
                </ResizablePanel>
                <ResizableHandle withHandle />
                <ResizablePanel defaultSize={35} minSize={20}>
                  <DetailPanel />
                </ResizablePanel>
              </ResizablePanelGroup>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-10 text-center space-y-4">
                <div className="bg-muted p-6 rounded-full">
                  <Share2 className="h-10 w-10 text-muted-foreground" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-xl font-semibold">선택된 노드가 없습니다</h3>
                  <p className="text-muted-foreground max-w-sm">
                    왼쪽 사이드바에서 메서드나 엔드포인트를 선택하여 호출 관계를 시각화해 보세요.
                  </p>
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="results" className="flex-1 m-0 overflow-auto">
            <div className="p-8 h-full bg-slate-50">
              <div className="mx-auto space-y-8">
                <div className="space-y-1">
                  <h2 className="text-2xl font-bold tracking-tight">Test Results</h2>
                  <p className="text-muted-foreground">생성된 테스트 시나리오 및 케이스 목록입니다.</p>
                </div>

                {isAgentRunning && happyCaseScenarios.length === 0 && integrationScenarios.length === 0 ? (
                  <Card className="border-2 border-primary/20 shadow-xl overflow-hidden bg-white/50 backdrop-blur-sm">
                    <LoadingProgress />
                  </Card>
                ) : (happyCaseScenarios.length > 0 || integrationScenarios.length > 0) ? (
                  <div className="space-y-8">
                    {happyCaseScenarios.length > 0 && (
                      <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <HappyCaseTableView />
                      </div>
                    )}

                    {integrationScenarios.length > 0 && (
                      <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                          <Activity className="h-5 w-5 text-blue-500" />
                          Integration Scenarios
                        </h3>
                        <Card className="border-2 border-primary/20 shadow-lg overflow-hidden">
                          <IntegrationScenarioView />
                        </Card>
                      </div>
                    )}
                  </div>
                ) : (
                  <Card className="items-center justify-center flex flex-col p-20 border-dashed border-2 bg-slate-50/50">
                    <div className="bg-muted p-4 rounded-full mb-4">
                      <TestTube className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <h3 className="text-xl font-semibold mb-2">생성된 결과가 없습니다</h3>
                    <p className="text-muted-foreground text-center max-w-md">
                      왼쪽 사이드바에서 메서드를 선택한 후 <strong>Happy Case 생성</strong> 버튼을 클릭하여 테스트 데이터를 생성해 보세요.
                    </p>
                  </Card>
                )}
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
