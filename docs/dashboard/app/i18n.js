const requested = new URLSearchParams(window.location.search).get("lang") || "auto";
const language = requested === "ko" || requested === "en"
  ? requested
  : navigator.language.toLowerCase().startsWith("ko") ? "ko" : "en";

const COPY = {
  en: {
    unknown: "Unknown", none: "None", waitingEvent: "The office is waiting for the next event.",
    providerProgress: "Provider progress {percent}%", providerUnknown: "Provider progress: unknown",
    connected: "Connecting", reconnecting: "Reconnecting", enterRun: "Enter a run ID.",
    displayError: "Display error: {message}", loadError: "Could not open the office: {message}", error: "Error",
    team: "Team", role: "Role", current: "Current", worker: "Worker", workers: "{count} agents",
    planTeam: "Planning", researchTeam: "Research", designTeam: "Design", implementTeam: "Implementation",
    verifyTeam: "Verification", idle: "Idle", work: "Working", talk: "Coordinating", blocked: "Needs review",
    complete: "Complete", coordination: "Team coordination", contributor: "Assigned work",
    currentTask: "Current task", noDescription: "No description", status: "Status", model: "Model",
    notUsed: "Not used", effort: "Effort", route: "Route", workerRun: "Worker run", noRecord: "No record",
    verification: "Verification", verificationSource: "Verification source", criteria: "Acceptance criteria",
    elapsed: "Elapsed", progress: "Progress", taskId: "Task ID", dependencies: "Dependencies",
    evidence: "Evidence", recentEvent: "Recent event", teamOnly: "Represents team state only",
    unassigned: "No assigned task", characterPool: "Character pool", visualOnly: "{count} characters · display only",
    lead: "Lead", teamLead: "Team lead", coordinating: "Coordinating", checking: "Checking status",
    omissionReason: "Why omitted", graphAgents: "Actual agents", independentRoot: "Independent root node",
    executionGraph: "Execution graph", time: "Time", description: "Description", proven: "Proven",
    notProven: "Evidence missing", failed: "Failed", notApplicable: "Not applicable",
    minutesSeconds: "{minutes}m {seconds}s", seconds: "{seconds}s", needsReviewCount: "{count} need review",
    workingCount: "{count} working", workComplete: "Work complete", waitingConnection: "Waiting to connect",
    graphSummary: "Execution graph", ready: "Ready", connectHelp: "Enter a run ID to see recorded progress in the office.",
    runId: "Run ID", connect: "Connect", demo: "View sample office", waitingRun: "Waiting for a run ID.",
    verifyZero: "Verified 0 / 0", close: "Close", selectedInfo: "Selected information", member: "member"
  },
  ko: {
    unknown: "알 수 없음", none: "없음", waitingEvent: "오피스가 다음 사건을 기다리고 있습니다.",
    providerProgress: "제공자 진행 {percent}%", providerUnknown: "제공자 진행: 알 수 없음",
    connected: "연결 중", reconnecting: "재연결", enterRun: "작업 ID를 입력해 주세요.",
    displayError: "표시 오류: {message}", loadError: "오피스 공간을 열지 못했습니다: {message}", error: "오류",
    team: "팀", role: "역할", current: "현재", worker: "작업자", workers: "{count}명",
    planTeam: "기획팀", researchTeam: "자료조사팀", designTeam: "설계팀", implementTeam: "구현팀",
    verifyTeam: "검증팀", idle: "대기", work: "작업 중", talk: "팀 조정 중", blocked: "확인 필요",
    complete: "완료", coordination: "팀 조정", contributor: "실제 작업 담당", currentTask: "현재 작업",
    noDescription: "설명 없음", status: "상태", model: "모델", notUsed: "사용 안 함", effort: "작업 강도",
    route: "실행 방식", workerRun: "작업자 실행", noRecord: "기록 없음", verification: "검증",
    verificationSource: "검증 출처", criteria: "완료 기준", elapsed: "경과 시간", progress: "진행률",
    taskId: "작업 ID", dependencies: "선행 작업", evidence: "근거", recentEvent: "최근 사건",
    teamOnly: "팀 상태만 대표합니다.", unassigned: "배정된 작업 없음", characterPool: "캐릭터 모음",
    visualOnly: "{count}명 · 화면 표현용", lead: "팀장", teamLead: "팀장", coordinating: "팀 조정 중",
    checking: "상태 확인 중", omissionReason: "사용하지 않는 이유", graphAgents: "실제 에이전트",
    independentRoot: "독립 시작 작업", executionGraph: "실행 구조", time: "시각", description: "설명",
    proven: "확인됨", notProven: "확인 근거 부족", failed: "충족하지 못함", notApplicable: "해당 없음",
    minutesSeconds: "{minutes}분 {seconds}초", seconds: "{seconds}초", needsReviewCount: "{count}건 확인 필요",
    workingCount: "{count}명 작업 중", workComplete: "작업 완료", waitingConnection: "연결 대기",
    graphSummary: "실행 그래프", ready: "준비", connectHelp: "작업 ID를 입력하면 기록된 진행 상황을 회사 안에서 확인할 수 있습니다.",
    runId: "작업 ID", connect: "연결", demo: "샘플 오피스 보기", waitingRun: "연결할 작업을 기다리고 있습니다.",
    verifyZero: "검증 0 / 0", close: "닫기", selectedInfo: "선택한 정보", member: "담당"
  },
};

function t(key, variables = {}) {
  return (COPY[language][key] || COPY.en[key] || key).replace(/\{(\w+)\}/g, (_, name) => variables[name] ?? "");
}

function catalogLabel(table, key, fallback) {
  return table?.[key]?.[language] || fallback || key || t("unknown");
}

export { catalogLabel, language, t };
