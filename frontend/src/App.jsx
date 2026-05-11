import { useEffect, useMemo, useReducer, useRef, useState } from "react";
// import { invoke } from "@forge/bridge";
import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Calculator,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
  FlaskConical,
  Gauge,
  GitBranch,
  LayoutDashboard,
  Layers,
  ListChecks,
  ListTodo,
  Loader2,
  Moon,
  Pencil,
  Play,
  Plus,
  Rocket,
  Send,
  Settings,
  ShieldAlert,
  Sparkles,
  Sun,
  Trash2,
  Undo2,
  UserCircle2,
  X,
  XCircle,
} from "lucide-react";

const PROJECTS = [
  "PAY-Platform Revamp",
  "Customer Onboarding 2026",
  "Core API Modernization",
];

const NAV_ITEMS = [
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Backlog AI", icon: ListTodo },
  { label: "Sprint AI", icon: Rocket },
  { label: "Estimation", icon: Calculator },
  { label: "Settings", icon: Settings },
];

const SIDEBAR_METRICS = [
  { label: "Current sprint", value: "Sprint 14" },
  { label: "Backlog", value: "23 tickets" },
  { label: "Last AI run", value: "Today, 14:32" },
  { label: "Team velocity / sprint", value: "42 SP" },
];

const MEETING_NOTES_PLACEHOLDER =
  "Sprint planning notes:\n- Users cannot retry card payment after timeout\n- Checkout needs FR invoice labels before release\n- Support asked for Jira tickets with failure reason codes";

const FIBONACCI_POINTS = [1, 2, 3, 5, 8, 13, 21];

const PIPELINE_TEMPLATE = [
  { id: 1, label: "Ticket Generator", icon: FileText, status: "pending" },
  { id: 2, label: "Anomaly Detector", icon: ShieldAlert, status: "pending" },
  { id: 3, label: "Effort Estimator", icon: Gauge, status: "pending" },
  { id: 4, label: "Subtasks Proposer", icon: ListChecks, status: "pending" },
  {
    id: 5,
    label: "Test Case Generator",
    icon: FlaskConical,
    status: "pending",
  },
];

const FILTERS = ["All", "Flagged", "Needs Review"];
const PRIORITIES = ["Critical", "High", "Medium", "Low"];
const ROLES = ["Frontend", "Backend", "QA", "DevOps"];
const TEST_TABS = ["Nominal", "Error", "Edge"];

const PRIORITY_CLASS = {
  Critical: "bg-red-50 text-red-700 border border-red-200",
  High: "bg-orange-50 text-orange-700 border border-orange-200",
  Medium: "bg-yellow-50 text-yellow-700 border border-yellow-200",
  Low: "bg-gray-100 text-gray-700 border border-gray-200",
};

const ROLE_CLASS = {
  Frontend: "bg-blue-50 text-blue-700 border border-blue-100",
  Backend: "bg-indigo-50 text-indigo-700 border border-indigo-100",
  QA: "bg-green-50 text-green-700 border border-green-100",
  DevOps: "bg-purple-50 text-purple-700 border border-purple-100",
};

const ANOMALY_CLASS = {
  Duplicate: "bg-red-50 text-red-700 border border-red-100",
  Conflict: "bg-orange-50 text-orange-700 border border-orange-100",
  Dependency: "bg-blue-50 text-blue-700 border border-blue-100",
};

const STATUS_CHIP_CLASS = {
  pending: "bg-gray-100 text-gray-600",
  running: "bg-blue-100 text-blue-700 animate-pulse",
  done: "bg-green-100 text-green-700",
  error: "bg-red-100 text-red-700",
};

const MOCK_TICKETS = [
  {
    id: "DRAFT-001",
    title: "Enable reusable promo codes on checkout",
    priority: "High",
    description:
      "As a shopper, I want to apply a campaign promo code during checkout and see live totals, so that I can confirm final pricing before payment.",
    acceptanceCriteria: [
      "Promo code field validates format before submission.",
      "Discount is recalculated instantly after valid promo code entry.",
      "Applied promo appears in order summary and final invoice payload.",
      "Invalid or expired promo code displays actionable message.",
    ],
    storyPoints: [3, 5, 8],
    confidence: 87,
    forcedReview: false,
    anomalies: [
      {
        type: "Duplicate",
        icon: "🔴",
        details:
          "Potential overlap with DRAFT-003 where discounted totals are also recalculated at order confirmation.",
      },
      {
        type: "Dependency",
        icon: "🔵",
        details:
          "Depends on payment API endpoint exposing normalized discount breakdown in response payload.",
      },
    ],
    subtasks: [
      {
        id: "S-001",
        title: "Design promo-code input state UX",
        role: "Frontend",
        effort: "0.25",
        order: 1,
      },
      {
        id: "S-002",
        title: "Add promo validation endpoint contract",
        role: "Backend",
        effort: "0.35",
        order: 2,
      },
      {
        id: "S-003",
        title: "Automate invalid/expired promo tests",
        role: "QA",
        effort: "0.20",
        order: 3,
      },
    ],
    testCases: [
      {
        id: "TC-001",
        type: "Nominal",
        summary: "Apply valid promo code with 10% discount",
        expected: "Order summary updates and payload includes promo metadata",
        criticality: "P1",
        execution: "Automated",
      },
      {
        id: "TC-002",
        type: "Error",
        summary: "Submit expired promo code",
        expected: "User sees expiry warning and totals remain unchanged",
        criticality: "P2",
        execution: "Manual",
      },
      {
        id: "TC-003",
        type: "Edge",
        summary: "Apply promo and switch cart currency",
        expected: "Discount recomputes with currency conversion constraints",
        criticality: "P2",
        execution: "Automated",
      },
      {
        id: "TC-004",
        type: "Nominal",
        summary: "Apply promo then remove it",
        expected: "Totals roll back and promo field returns to neutral state",
        criticality: "P3",
        execution: "Automated",
      },
    ],
  },
  {
    id: "DRAFT-002",
    title: "Introduce card retry flow after payment timeout",
    priority: "Medium",
    description:
      "As a customer, I need a safe retry option when payment authorization times out, so I can complete checkout without duplicating charges.",
    acceptanceCriteria: [
      "Timeout state displays retry and cancel actions.",
      "Retry reuses the same order draft and idempotency key.",
      "Duplicate-charge protection blocks second capture call.",
    ],
    storyPoints: [2, 3, 5],
    confidence: 46,
    forcedReview: true,
    anomalies: [
      {
        type: "Conflict",
        icon: "🟠",
        details:
          "Retry window currently conflicts with PCI timeout standard in payment compliance policy v2.",
      },
    ],
    subtasks: [
      {
        id: "S-004",
        title: "Add timeout CTA module in checkout page",
        role: "Frontend",
        effort: "0.30",
        order: 1,
      },
      {
        id: "S-005",
        title: "Implement idempotent retry endpoint",
        role: "Backend",
        effort: "0.40",
        order: 2,
      },
      {
        id: "S-006",
        title: "Track timeout and retry metrics",
        role: "DevOps",
        effort: "0.15",
        order: 3,
      },
      {
        id: "S-007",
        title: "Validate no double capture on retry",
        role: "QA",
        effort: "0.25",
        order: 4,
      },
    ],
    testCases: [
      {
        id: "TC-005",
        type: "Nominal",
        summary: "Timeout then retry succeeds within allowed window",
        expected: "Single successful capture tied to original order draft",
        criticality: "P1",
        execution: "Automated",
      },
      {
        id: "TC-006",
        type: "Error",
        summary: "Timeout then retry after window expiry",
        expected: "Retry disabled and user redirected to payment selection",
        criticality: "P2",
        execution: "Manual",
      },
      {
        id: "TC-007",
        type: "Edge",
        summary: "User clicks retry multiple times quickly",
        expected: "System deduplicates requests and processes one capture only",
        criticality: "P1",
        execution: "Automated",
      },
    ],
  },
  {
    id: "DRAFT-003",
    title: "Generate payment failure insights for support dashboard",
    priority: "Critical",
    description:
      "As a support lead, I need structured failure insights in Jira-linked incidents so we can triage payment drops with clear root-cause hints.",
    acceptanceCriteria: [
      "Failed transactions are grouped by reason code.",
      "Each incident includes timeline and impacted region.",
      "Support dashboard highlights spikes over baseline threshold.",
    ],
    storyPoints: [5, 8, 13],
    confidence: 79,
    forcedReview: false,
    anomalies: [],
    subtasks: [
      {
        id: "S-008",
        title: "Create error code aggregation service",
        role: "Backend",
        effort: "0.45",
        order: 1,
      },
      {
        id: "S-009",
        title: "Build failure heatmap module",
        role: "Frontend",
        effort: "0.30",
        order: 2,
      },
      {
        id: "S-010",
        title: "Configure alert thresholds and routing",
        role: "DevOps",
        effort: "0.15",
        order: 3,
      },
    ],
    testCases: [
      {
        id: "TC-008",
        type: "Nominal",
        summary: "Dashboard displays grouped failures by reason code",
        expected: "Cards reflect real-time grouped counts and trend deltas",
        criticality: "P1",
        execution: "Automated",
      },
      {
        id: "TC-009",
        type: "Error",
        summary: "Missing region metadata in incident payload",
        expected: "Incident still appears with fallback region marker",
        criticality: "P2",
        execution: "Manual",
      },
      {
        id: "TC-010",
        type: "Edge",
        summary: "Sudden 5x spike in failed captures",
        expected: "Spike alert triggers and highlighted panel is visible",
        criticality: "P1",
        execution: "Automated",
      },
      {
        id: "TC-011",
        type: "Nominal",
        summary: "Create Jira incident from highlighted failure cluster",
        expected: "Jira issue contains summary, reason codes, and timeline",
        criticality: "P2",
        execution: "Manual",
      },
    ],
  },
  {
    id: "DRAFT-004",
    title: "Support localized invoice labels for FR and EN",
    priority: "Low",
    description:
      "As finance operations, we need invoice labels in French and English to streamline customer support and compliance audits.",
    acceptanceCriteria: [
      "Invoice label locale follows account language preference.",
      "Fallback to English if translation key is missing.",
      "PDF and email invoice templates remain synchronized.",
    ],
    storyPoints: [1, 2, 3],
    confidence: 63,
    forcedReview: false,
    anomalies: [
      {
        type: "Dependency",
        icon: "🔵",
        details:
          "Blocked until translation catalog service publishes the FR namespace for invoice tags.",
      },
    ],
    subtasks: [
      {
        id: "S-011",
        title: "Update invoice i18n key map",
        role: "Frontend",
        effort: "0.25",
        order: 1,
      },
      {
        id: "S-012",
        title: "Expose localized labels in invoice API",
        role: "Backend",
        effort: "0.35",
        order: 2,
      },
    ],
    testCases: [
      {
        id: "TC-012",
        type: "Nominal",
        summary: "Invoice generated for FR locale account",
        expected: "All supported labels appear in French",
        criticality: "P2",
        execution: "Automated",
      },
      {
        id: "TC-013",
        type: "Error",
        summary: "Missing translation key in FR namespace",
        expected: "Fallback label displays in English without layout break",
        criticality: "P3",
        execution: "Manual",
      },
      {
        id: "TC-014",
        type: "Edge",
        summary: "Switch account locale after invoice draft generated",
        expected: "Regeneration applies updated locale labels end-to-end",
        criticality: "P2",
        execution: "Automated",
      },
    ],
  },
].map((ticket) => ({
  ...ticket,
  status: "pending",
  previousStatus: "pending",
  overrideStoryPoints: null,
}));

function ticketsReducer(state, action) {
  switch (action.type) {
    case "replace":
      return action.tickets;
    case "accept":
      return state.map((ticket) =>
        ticket.id === action.id ? { ...ticket, status: "accepted" } : ticket,
      );
    case "reject":
      return state.map((ticket) =>
        ticket.id === action.id
          ? {
            ...ticket,
            previousStatus:
              ticket.status === "rejected" ? "pending" : ticket.status,
            status: "rejected",
          }
          : ticket,
      );
    case "undoReject":
      return state.map((ticket) =>
        ticket.id === action.id
          ? {
            ...ticket,
            status: ticket.previousStatus || "pending",
            previousStatus: "pending",
          }
          : ticket,
      );
    case "bulkAccept":
      return state.map((ticket) => ({ ...ticket, status: "accepted" }));
    case "bulkReject":
      return state.map((ticket) => ({
        ...ticket,
        previousStatus:
          ticket.status === "rejected" ? "pending" : ticket.status,
        status: "rejected",
      }));
    case "updateTitle":
      return state.map((ticket) =>
        ticket.id === action.id ? { ...ticket, title: action.title } : ticket,
      );
    case "saveEdit":
      return state.map((ticket) =>
        ticket.id === action.ticket.id
          ? {
            ...ticket,
            ...action.ticket,
            status: "accepted",
            modified: true,
          }
          : ticket,
      );
    default:
      return state;
  }
}

function clampPriority(priority) {
  return PRIORITIES.includes(priority) ? priority : "Medium";
}

function buildStoryPointRange(storyPoints, fallbackRange) {
  const probable = Number(storyPoints);
  if (!Number.isFinite(probable) || probable <= 0) {
    return fallbackRange;
  }

  const index = FIBONACCI_POINTS.findIndex((point) => point >= probable);
  const safeIndex = index === -1 ? FIBONACCI_POINTS.length - 1 : index;
  const min = FIBONACCI_POINTS[Math.max(0, safeIndex - 1)];
  const max =
    FIBONACCI_POINTS[Math.min(FIBONACCI_POINTS.length - 1, safeIndex + 1)];
  return [min, FIBONACCI_POINTS[safeIndex], max];
}

function inferRole(component) {
  if (ROLES.includes(component)) return component;
  if (component === "Infrastructure") return "DevOps";
  return "Backend";
}

function normalizeSubtasks(apiTicket, fallback, ticketId) {
  if (
    Array.isArray(apiTicket.subtasks_detailed) &&
    apiTicket.subtasks_detailed.length > 0
  ) {
    return apiTicket.subtasks_detailed.map((subtask, index) => ({
      id: `${ticketId}-S-${index + 1}`,
      title: subtask.title,
      role: subtask.assignedRole,
      effort: subtask.effortFraction.toFixed(2),
      order: subtask.order,
    }));
  }
  return [];
}

function normalizeAnomalies(apiTicket, fallback) {
  const derived = [];
  const flags = apiTicket.anomaly_flags || [];
  for (const flag of flags) {
    if (flag.isDuplicate) {
      derived.push({
        type: "Duplicate",
        icon: "🔴",
        details: `Duplicate of ${flag.duplicateOf}. Reason: ${flag.duplicateReason || "High textual similarity found."}`,
      });
    }
    if (flag.conflicts && flag.conflicts.length > 0) {
      flag.conflicts.forEach((c) =>
        derived.push({
          type: "Conflict",
          icon: "🟠",
          details: `Conflicts with ${c.withTicket}: ${c.reason}`,
        }),
      );
    }
    if (flag.dependencies && flag.dependencies.length > 0) {
      flag.dependencies.forEach((d) =>
        derived.push({ type: "Dependency", icon: "🔵", details: d }),
      );
    }
  }
  return derived.length > 0 ? derived : [];
}

function normalizeTestCases(apiTicket) {
  if (Array.isArray(apiTicket.test_cases) && apiTicket.test_cases.length > 0) {
    return apiTicket.test_cases.map((tc, index) => ({
      id: tc.id || `TC-${index + 1}`,
      type:
        tc.type === "nominal"
          ? "Nominal"
          : tc.type === "error"
            ? "Error"
            : "Edge",
      summary: tc.title,
      expected: tc.expectedResult,
      criticality:
        tc.criticality === "critical"
          ? "P1"
          : tc.criticality === "major"
            ? "P2"
            : "P3",
      execution: tc.executionType === "automated" ? "Automated" : "Manual",
    }));
  }
  return [];
}

function adaptApiTickets(apiTickets, confidenceThreshold) {
  return apiTickets.map((apiTicket, index) => {
    const ticketId = `DRAFT-${String(index + 1).padStart(3, "0")}`;
    const confidence = Number(apiTicket.confidence ?? 70);

    const descriptionText =
      apiTicket.description +
      (apiTicket.non_functional_requirements?.length
        ? "\n\n**Non-Functional Requirements:**\n- " +
        apiTicket.non_functional_requirements.join("\n- ")
        : "");

    // Use the actual estimation if available, otherwise fallback array
    const spRange = apiTicket.estimations?.pertEstimate
      ? [
        apiTicket.estimations.min,
        apiTicket.estimations.pertEstimate,
        apiTicket.estimations.max,
      ]
      : [3, 5, 8];
    const rationale =
      apiTicket.estimations?.rationale || "No rationale provided by backend.";

    return {
      id: ticketId,
      title: apiTicket.title,
      priority: clampPriority(apiTicket.priority),
      description: descriptionText,
      acceptanceCriteria: apiTicket.acceptance_criteria || [],
      storyPoints: spRange,
      rationale: rationale,
      confidence,
      forcedReview:
        Boolean(apiTicket.forced_review) || confidence < confidenceThreshold,
      anomalies: normalizeAnomalies(apiTicket, null),
      subtasks: normalizeSubtasks(apiTicket, null, ticketId),
      testCases: normalizeTestCases(apiTicket),
      status: "pending",
      previousStatus: "pending",
      overrideStoryPoints: null,
    };
  });
}

function getStoryPointLabel(ticket) {
  if (ticket.overrideStoryPoints) {
    return `Override ${ticket.overrideStoryPoints} SP`;
  }
  // Instead of showing 3 numbers, just show the exact predicted PERT effort (the middle one)
  return `${ticket.storyPoints[1]} SP`;
}

function App() {
  const [theme, setTheme] = useState("dark");
  const [activeNav, setActiveNav] = useState("Backlog AI");
  const [selectedProject, setSelectedProject] = useState(PROJECTS[0]);
  const [notesInput, setNotesInput] = useState("");
  const [submittedPrompt, setSubmittedPrompt] = useState("");
  const [language, setLanguage] = useState("EN");
  const [maxTickets, setMaxTickets] = useState(8);
  const [confidenceThreshold, setConfidenceThreshold] = useState(70);
  const [view, setView] = useState("board");
  const [pipelineSteps, setPipelineSteps] = useState(PIPELINE_TEMPLATE);
  const [activeFilter, setActiveFilter] = useState("All");
  // Initialize with empty array for production
  const [tickets, dispatch] = useReducer(ticketsReducer, []);
  const [undoVisibleByTicket, setUndoVisibleByTicket] = useState({});
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editTicket, setEditTicket] = useState(null);
  const [pushConfirmOpen, setPushConfirmOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState("");
  const [apiError, setApiError] = useState("");
  const pipelineTimersRef = useRef([]);
  const undoTimersRef = useRef({});
  const toastTimerRef = useRef(null);

  const filteredTickets = useMemo(() => {
    if (activeFilter === "All") return tickets;
    if (activeFilter === "Flagged")
      return tickets.filter((ticket) => ticket.anomalies.length > 0);
    if (activeFilter === "Needs Review") {
      return tickets.filter(
        (ticket) => ticket.forcedReview || ticket.confidence < 50,
      );
    }
    return tickets;
  }, [activeFilter, tickets]);

  const acceptedCount = tickets.filter(
    (ticket) => ticket.status === "accepted",
  ).length;
  const rejectedCount = tickets.filter(
    (ticket) => ticket.status === "rejected",
  ).length;
  const actionedCount = acceptedCount + rejectedCount;
  const wordCount = useMemo(() => {
    const trimmed = notesInput.trim();
    return trimmed ? trimmed.split(/\s+/).length : 0;
  }, [notesInput]);
  const canGenerate = wordCount > 0;

  useEffect(() => {
    return () => {
      pipelineTimersRef.current.forEach((timer) => clearTimeout(timer));
      Object.values(undoTimersRef.current).forEach((timer) =>
        clearTimeout(timer),
      );
      if (toastTimerRef.current) {
        clearTimeout(toastTimerRef.current);
      }
    };
  }, []);

  function applyStepStatuses(nextStatuses) {
    setPipelineSteps((current) =>
      current.map((step) => ({
        ...step,
        status: nextStatuses[step.id] || step.status,
      })),
    );
  }

  function queuePipelineStep(delay, callback) {
    const timer = setTimeout(callback, delay);
    pipelineTimersRef.current.push(timer);
  }

  function startPipeline() {
    pipelineTimersRef.current.forEach((timer) => clearTimeout(timer));
    pipelineTimersRef.current = [];
    setView("pipeline");
    setPipelineSteps(
      PIPELINE_TEMPLATE.map((step) => ({
        ...step,
        status: step.id === 1 ? "running" : "pending",
      })),
    );

    return new Promise((resolve) => {
      queuePipelineStep(800, () =>
        applyStepStatuses({ 1: "done", 2: "running" }),
      );
      queuePipelineStep(1600, () =>
        applyStepStatuses({ 2: "done", 3: "running" }),
      );
      queuePipelineStep(2400, () =>
        applyStepStatuses({ 3: "done", 4: "running", 5: "running" }),
      );
      queuePipelineStep(3400, () =>
        applyStepStatuses({ 4: "done", 5: "done" }),
      );
      queuePipelineStep(4000, () => {
        setPipelineSteps(
          PIPELINE_TEMPLATE.map((step) => ({ ...step, status: "done" })),
        );
        resolve();
      });
    });
  }

  async function requestTicketsFromApi(promptText) {
    try {
      const response = await fetch(
        "http://localhost:8000/api/generate-tickets",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            request: promptText,
            language: language,
          }),
        },
      );

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }
      if (!Array.isArray(data.tickets) || data.tickets.length === 0) {
        throw new Error("The backend returned no tickets.");
      }

      return adaptApiTickets(
        data.tickets.slice(0, maxTickets),
        confidenceThreshold,
      );
    } catch (err) {
      throw err;
    }
  }

  useEffect(() => {
    // If loaded inside a Jira iframe, auto-resize to fit the content
    if (window.AP && window.AP.resize) {
      window.AP.resize("100%", "100%");
    }
  }, [view, tickets.length]);

  async function handleGenerate() {
    if (!canGenerate) return;
    setApiError("");
    const promptText = notesInput;
    setSubmittedPrompt(promptText);
    setNotesInput("");
    const inputElement = document.getElementById("notes-input");
    if (inputElement) {
      inputElement.style.height = "auto";
    }
    const pipelineDone = startPipeline();

    try {
      const generatedTickets = await requestTicketsFromApi(promptText);
      await pipelineDone;
      dispatch({ type: "replace", tickets: generatedTickets });
      setActiveFilter("All");
      setView("board");
    } catch (error) {
      await pipelineDone;
      setPipelineSteps((current) =>
        current.map((step) =>
          step.status === "running" ? { ...step, status: "error" } : step,
        ),
      );
      setApiError(
        error instanceof Error ? error.message : "Unable to generate tickets.",
      );
      setView("board");
    }
  }

  function handleRejectTicket(ticketId) {
    dispatch({ type: "reject", id: ticketId });
    setUndoVisibleByTicket((current) => ({ ...current, [ticketId]: true }));
    if (undoTimersRef.current[ticketId]) {
      clearTimeout(undoTimersRef.current[ticketId]);
    }
    undoTimersRef.current[ticketId] = setTimeout(() => {
      setUndoVisibleByTicket((current) => ({ ...current, [ticketId]: false }));
    }, 3000);
  }

  function handleUndoReject(ticketId) {
    dispatch({ type: "undoReject", id: ticketId });
    if (undoTimersRef.current[ticketId]) {
      clearTimeout(undoTimersRef.current[ticketId]);
    }
    setUndoVisibleByTicket((current) => ({ ...current, [ticketId]: false }));
  }

  function openEditModal(ticket) {
    setEditTicket({
      ...ticket,
      acceptanceCriteria: [...ticket.acceptanceCriteria],
      subtasks: ticket.subtasks.map((subtask) => ({ ...subtask })),
    });
    setEditModalOpen(true);
    requestAnimationFrame(() =>
      window.scrollTo({ top: 0, behavior: "smooth" }),
    );
  }

  function saveEditTicket() {
    if (!editTicket) return;
    const normalizedSubtasks = editTicket.subtasks.map((subtask, index) => ({
      ...subtask,
      order: index + 1,
    }));
    dispatch({
      type: "saveEdit",
      ticket: { ...editTicket, subtasks: normalizedSubtasks },
    });
    setEditModalOpen(false);
    setEditTicket(null);
  }

  function handlePushToJira() {
    const createdCount = acceptedCount;
    setPushConfirmOpen(false);
    setToastMessage(`${createdCount} tickets created in Jira ✓`);
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
    }
    toastTimerRef.current = setTimeout(() => {
      setToastMessage("");
    }, 3200);
  }

  return (
    <div className={theme === "dark" ? "dark" : ""}>
      <div className="min-h-screen bg-[#F9F9F8] font-sans text-gray-900 transition-all duration-200">
        <div className="pointer-events-none fixed inset-0 overflow-hidden">
          {/* Removed decorative blurs */}
        </div>

        <header className="relative z-10 border-b border-gray-100 bg-white">
          <div className="mx-auto flex max-w-[1200px] items-center justify-between px-4 py-3 sm:px-6">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="rounded-xl bg-blue-600 p-2 text-white shadow-lg shadow-blue-100">
                  <Layers className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-base font-bold tracking-tight">
                    Jira Copilot
                  </p>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-blue-600">
                    AI Agent Active
                  </p>
                </div>
              </div>
              <div className="hidden items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm md:flex shadow-sm">
                <span className="text-[10px] font-bold uppercase tracking-wide text-gray-400">
                  Project
                </span>
                <select
                  className="bg-transparent text-sm font-semibold outline-none"
                  value={selectedProject}
                  onChange={(event) => setSelectedProject(event.target.value)}
                >
                  {PROJECTS.map((project) => (
                    <option
                      key={project}
                      value={project}
                      className="text-gray-900"
                    >
                      {project}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 rounded-xl border border-gray-100 bg-gray-50 px-3 py-1.5 shadow-inner">
                <UserCircle2 className="h-5 w-5 text-blue-600" />
                <span className="text-sm font-bold text-gray-700">
                  Product Owner
                </span>
              </div>
            </div>
          </div>
        </header>

        <div className="relative z-10 mx-auto flex max-w-[1200px] gap-6 px-4 py-6 sm:px-6 mb-32">
          <main className="w-full space-y-6">
            {editModalOpen && editTicket ? (
              <EditModal
                ticket={editTicket}
                setTicket={setEditTicket}
                onCancel={() => {
                  setEditModalOpen(false);
                  setEditTicket(null);
                }}
                onSave={saveEditTicket}
              />
            ) : (
              <>
                {view === "pipeline" ? null : (
                  // Used to be here, but we deleted it because we embedded it inside the floating toolbar
                  <></>
                )}

                {view === "board" && tickets.length === 0 && (
                  <div
                    className={
                      view === "pipeline" ? "h-0 invisible" : "h-[60vh]"
                    }
                  ></div>
                )}

                {submittedPrompt && (view === "board" || view === "pipeline") && (
                  <div className="mb-8 flex flex-col items-end space-y-2">
                    <div className="flex items-center gap-2 text-sm text-gray-500 font-semibold mb-1 mr-2">
                      <UserCircle2 className="w-5 h-5" />
                      You
                    </div>
                    <div className="max-w-[85%] rounded-3xl rounded-tr-sm bg-gray-100 px-6 py-4 text-gray-800 shadow-sm border border-gray-200">
                      <p className="whitespace-pre-wrap text-base leading-relaxed">
                        {submittedPrompt}
                      </p>
                    </div>
                  </div>
                )}

                {view === "board" && tickets.length > 0 && (
                  <section className="space-y-4 rounded-3xl border border-gray-100 bg-white p-6 shadow-xl shadow-blue-50/50">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h3 className="text-2xl font-bold tracking-tight text-gray-900 leading-tight">
                        AI Generated Backlog ({tickets.length} tickets)
                      </h3>
                      <button
                        type="button"
                        onClick={() => dispatch({ type: "bulkAccept" })}
                        className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-bold text-blue-700 transition-all duration-200 hover:bg-blue-100 hover:scale-[1.02]"
                      >
                        Accept All Suggestions
                      </button>
                    </div>

                    <div className="flex flex-wrap gap-2 rounded-2xl border border-gray-50 bg-gray-50/50 p-1.5">
                      {FILTERS.map((filter) => (
                        <button
                          key={filter}
                          type="button"
                          onClick={() => setActiveFilter(filter)}
                          className={`rounded-xl px-4 py-2 text-sm font-bold transition-all duration-200 ${activeFilter === filter
                              ? "bg-blue-600 text-white shadow-md shadow-blue-100"
                              : "text-gray-500 hover:bg-white hover:text-gray-900"
                            }`}
                        >
                          {filter}
                        </button>
                      ))}
                    </div>

                    <div className="space-y-4">
                      {filteredTickets.map((ticket) => (
                        <div key={ticket.id} className="space-y-2">
                          <TicketCard
                            ticket={ticket}
                            onAccept={() =>
                              dispatch({ type: "accept", id: ticket.id })
                            }
                            onReject={() => handleRejectTicket(ticket.id)}
                            onUndoReject={() => handleUndoReject(ticket.id)}
                            onEdit={() => openEditModal(ticket)}
                            onInlineTitleSave={(nextTitle) =>
                              dispatch({
                                type: "updateTitle",
                                id: ticket.id,
                                title: nextTitle,
                              })
                            }
                            showUndo={Boolean(undoVisibleByTicket[ticket.id])}
                          />
                          <div className="ml-4 pl-4 border-l-2 border-blue-200 py-2">
                            <div className="flex items-center gap-2 text-sm text-blue-600 mb-1">
                              <Sparkles className="w-4 h-4" />
                              <strong>AI Agent Rationale</strong>
                            </div>
                            <p className="text-sm text-gray-600">
                              {ticket.rationale}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </>
            )}
          </main>
        </div>

        {apiError && (
          <div className="mx-auto max-w-[1600px] mb-4">
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {apiError}
            </div>
          </div>
        )}

        {/* Floating Input Chatbot UI */}
        <div
          className={`fixed bottom-0 left-0 right-0 z-40 transition-all duration-300 ${tickets.length === 0 && view !== "pipeline" ? "top-0 flex items-center justify-center bg-[#F9F9F8]" : "border-t border-gray-200 bg-white py-3 h-fit"}`}
        >
          <div
            className={`mx-auto flex flex-col gap-4 relative transition-all duration-300 w-full px-4 ${tickets.length === 0 && view !== "pipeline" ? "max-w-[800px]" : "max-w-[1200px]"}`}
          >
            {tickets.length === 0 && view !== "pipeline" && (
              <div className="flex flex-col items-center justify-center text-center space-y-6 mb-4">
                <div className="bg-white p-4 rounded-3xl shadow-sm border border-gray-100">
                  <Layers className="w-12 h-12 text-blue-600" />
                </div>
                <h2 className="text-4xl font-bold text-gray-900 tracking-tight">
                  Bonjour, how can I help you today?
                </h2>
                <p className="text-lg text-gray-500 max-w-lg leading-relaxed font-medium">
                  Paste your meeting notes or describe a feature. I'll transform
                  it into structured, estimated Jira tickets instantly.
                </p>
              </div>
            )}

            <div className="relative group w-full flex flex-col bg-white rounded-[24px] border border-gray-200 shadow-sm focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-50/50 transition-all duration-200">
              <textarea
                id="notes-input"
                value={notesInput}
                onChange={(event) => {
                  setNotesInput(event.target.value);
                  if (apiError) setApiError("");
                  // Auto-resize
                  event.target.style.height = "auto";
                  event.target.style.height = event.target.scrollHeight + "px";
                }}
                disabled={view === "pipeline"}
                placeholder="Message Copilot AI..."
                rows={1}
                style={{ maxHeight: "300px" }}
                className="w-full resize-none rounded-t-[24px] bg-transparent px-6 py-4 text-base font-medium text-gray-900 leading-relaxed outline-none transition-all duration-200 placeholder:text-gray-400"
              />

              {view === "pipeline" && (
                <div className="px-6 py-3 bg-gray-50/50 border-t border-gray-100 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                    <span className="text-sm font-bold text-blue-700 animate-pulse">
                      {pipelineSteps.find((s) => s.status === "running")
                        ?.name || "Processing..."}
                    </span>
                  </div>
                  <div className="flex gap-1.5">
                    {pipelineSteps.map((step) => (
                      <div
                        key={step.id}
                        className={`h-1.5 w-1.5 rounded-full transition-colors duration-300 ${step.status === "done"
                            ? "bg-green-500"
                            : step.status === "running"
                              ? "bg-blue-500 animate-pulse"
                              : "bg-gray-200"
                          }`}
                      />
                    ))}
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between px-4 pb-3 pt-1 border-t border-gray-50">
                <div className="flex items-center gap-1">
                  <button className="p-2 text-gray-400 hover:bg-gray-100 rounded-lg transition-colors">
                    <Plus className="w-5 h-5" />
                  </button>
                </div>

                <div className="flex items-center gap-4">
                  <button
                    type="button"
                    onClick={handleGenerate}
                    disabled={!canGenerate || view === "pipeline"}
                    className={`flex items-center justify-center rounded-xl h-9 px-4 transition-all duration-300 font-bold ${canGenerate && view !== "pipeline"
                        ? "bg-[#D97757] text-white hover:opacity-90 active:scale-95 shadow-sm"
                        : "bg-gray-100 text-gray-400 cursor-not-allowed"
                      }`}
                  >
                    {view === "pipeline" ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ArrowUp className="w-4 h-4 font-bold" />
                    )}
                  </button>
                </div>
              </div>
            </div>

            {tickets.length === 0 && view !== "pipeline" && (
              <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
                {["Code", "Analysis", "Write", "Architecture"].map((tag) => (
                  <button
                    key={tag}
                    className="px-5 py-2 rounded-full border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 transition-colors"
                  >
                    {tag}
                  </button>
                ))}
              </div>
            )}

            {actionedCount > 0 && tickets.length > 0 && (
              <div className="flex justify-between items-center mt-2 pl-4">
                <p className="text-sm text-gray-500 font-bold">
                  {acceptedCount} Selected for Jira
                </p>
                <button
                  type="button"
                  onClick={() => setPushConfirmOpen(true)}
                  disabled={acceptedCount === 0}
                  className="rounded-xl bg-blue-600 px-6 py-2.5 font-bold text-white hover:bg-blue-700 disabled:opacity-50 shadow-md shadow-blue-100 transition-all hover:scale-[1.02]"
                >
                  Push to Jira ({acceptedCount})
                </button>
              </div>
            )}
          </div>
        </div>

        {pushConfirmOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/55 p-4">
            <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-5 shadow-soft transition-all duration-200 dark:border-gray-700 dark:bg-gray-900">
              <h4 className="text-lg font-semibold">Confirm Jira Submission</h4>
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                You are about to create {acceptedCount} tickets in Jira for{" "}
                <span className="font-semibold">{selectedProject}</span>.
              </p>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setPushConfirmOpen(false)}
                  className="rounded-xl border border-gray-300 px-3 py-2 text-sm font-medium transition-all duration-200 hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handlePushToJira}
                  className="rounded-xl bg-green-600 px-3 py-2 text-sm font-semibold text-white transition-all duration-200 hover:bg-green-700"
                >
                  Confirm & Push
                </button>
              </div>
            </div>
          </div>
        )}

        {toastMessage && (
          <div className="fixed right-4 top-4 z-[60] rounded-xl bg-green-600 px-4 py-2 text-sm font-semibold text-white shadow-soft">
            {toastMessage}
          </div>
        )}
      </div>
    </div>
  );
}

function PipelineTracker({ steps, embedded = false }) {
  function statusIcon(status) {
    if (status === "done")
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    if (status === "running")
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    if (status === "error") return <XCircle className="h-4 w-4 text-red-500" />;
    return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
  }

  return (
    <section
      className={`rounded-2xl border border-gray-200 p-4 transition-all duration-200 dark:border-gray-700 ${embedded
          ? "bg-gray-50 dark:bg-gray-950"
          : "bg-white shadow-soft dark:bg-gray-900"
        }`}
    >
      <div className="mb-4 flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-blue-500" />
        <h3 className="text-lg font-semibold">Pipeline Progress Tracker</h3>
      </div>

      <div className="flex flex-col gap-3 xl:flex-row xl:items-stretch">
        {steps.slice(0, 3).map((step, index) => (
          <div
            key={step.id}
            className="flex min-w-0 flex-1 items-stretch gap-3"
          >
            <PipelineNode step={step} statusIcon={statusIcon} />
            {index < 2 && (
              <div className="hidden items-center text-gray-400 dark:text-gray-600 xl:flex">
                <ArrowRight className="h-5 w-5" />
              </div>
            )}
          </div>
        ))}
        <div className="hidden items-center text-gray-400 dark:text-gray-600 xl:flex">
          <GitBranch className="h-5 w-5" />
        </div>
        <div className="grid min-w-0 flex-[1.4] gap-3 rounded-2xl border border-dashed border-gray-300 p-3 dark:border-gray-700 sm:grid-cols-2">
          {steps.slice(3).map((step) => (
            <PipelineNode key={step.id} step={step} statusIcon={statusIcon} />
          ))}
        </div>
      </div>
    </section>
  );
}

function PipelineNode({ step, statusIcon }) {
  const Icon = step.icon;
  const isRunning = step.status === "running";
  return (
    <div
      className={`min-h-[92px] w-full rounded-xl border border-gray-200 bg-white p-3 transition-all duration-200 dark:border-gray-700 dark:bg-gray-900 ${isRunning ? "ring-2 ring-blue-500/40" : ""
        }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div
            className={`rounded-lg p-2 ${isRunning
                ? "bg-blue-600 text-white animate-pulse"
                : "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-200"
              }`}
          >
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold">
              {isRunning && (
                <span className="relative inline-flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-500 opacity-60" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-blue-600" />
                </span>
              )}
              {step.label}
            </p>
            <div className="mt-1 flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
              {statusIcon(step.status)}
              <span
                className={`rounded-full px-2 py-0.5 capitalize ${STATUS_CHIP_CLASS[step.status]}`}
              >
                {step.status}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TicketCard({
  ticket,
  onAccept,
  onReject,
  onUndoReject,
  onEdit,
  onInlineTitleSave,
  showUndo,
}) {
  const [editingTitle, setEditingTitle] = useState(false);
  const [draftTitle, setDraftTitle] = useState(ticket.title);
  const [showDescription, setShowDescription] = useState(true);
  const [showCriteria, setShowCriteria] = useState(true);
  const [showSubtasks, setShowSubtasks] = useState(true);
  const [showTests, setShowTests] = useState(true);
  const [activeTestTab, setActiveTestTab] = useState("Nominal");
  const [openFlag, setOpenFlag] = useState("");

  useEffect(() => {
    setDraftTitle(ticket.title);
  }, [ticket.title]);

  const visibleTests = ticket.testCases.filter(
    (testCase) => testCase.type === activeTestTab,
  );

  function commitTitle() {
    const normalized = draftTitle.trim();
    if (normalized && normalized !== ticket.title) {
      onInlineTitleSave(normalized);
    }
    setDraftTitle(
      ticket.title === normalized ? ticket.title : normalized || ticket.title,
    );
    setEditingTitle(false);
  }

  const leftBorderColor =
    ticket.priority === "Critical"
      ? "border-l-red-600"
      : ticket.priority === "High"
        ? "border-l-orange-500"
        : ticket.priority === "Medium"
          ? "border-l-yellow-500"
          : "border-l-blue-500";

  return (
    <article
      className={`rounded-lg border border-gray-200 border-l-[6px] bg-white p-5 shadow-sm transition-all duration-200 ${leftBorderColor} ${ticket.status === "rejected" ? "opacity-55" : "opacity-100"
        }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-gray-500">
            <span className="text-gray-900">{ticket.id}</span>
            <span
              className={`inline-block px-1.5 py-0.5 rounded text-[10px] bg-gray-100`}
            >
              {ticket.priority}
            </span>
            {ticket.forcedReview && (
              <span className="inline-flex items-center gap-1 rounded bg-yellow-100 px-1.5 py-0.5 text-yellow-800">
                <AlertTriangle className="h-3 w-3" />
                FORCED REVIEW
              </span>
            )}
          </div>
          {editingTitle ? (
            <input
              value={draftTitle}
              autoFocus
              onChange={(event) => setDraftTitle(event.target.value)}
              onBlur={commitTitle}
              onKeyDown={(event) => {
                if (event.key === "Enter") commitTitle();
              }}
              className="w-full rounded border border-blue-400 bg-white px-2 py-1 text-lg font-medium outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-500"
            />
          ) : (
            <button
              type="button"
              onClick={() => setEditingTitle(true)}
              className="text-left text-lg font-medium text-gray-900 transition-colors hover:text-blue-600"
            >
              {ticket.title}
            </button>
          )}
        </div>
      </div>

      <div className="mt-4 mb-4 flex items-center justify-between text-xs text-gray-500">
        <div className="w-1/2 flex flex-col gap-1">
          <div className="flex justify-between items-center text-[11px] font-bold uppercase tracking-wider text-gray-500">
            <span>AI Confidence</span>
            <span
              className={
                ticket.confidence < 60 ? "text-yellow-600" : "text-green-600"
              }
            >
              {ticket.confidence}%
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full ${ticket.confidence < 60 ? "bg-yellow-500" : "bg-green-500"}`}
              style={{ width: `${ticket.confidence}%` }}
            ></div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded bg-gray-100 border border-gray-200 px-2 py-1 font-semibold text-gray-700">
            {getStoryPointLabel(ticket)}
          </span>
        </div>
      </div>

      <div className="mt-4 space-y-5">
        <section>
          <div className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2">
            User Story
          </div>
          <div className="rounded bg-[#f4f5f7] p-3 text-sm leading-6 text-gray-800">
            {ticket.description}
          </div>
        </section>

        <section>
          <div className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2">
            Acceptance Criteria
          </div>
          <ul className="list-disc space-y-1 pl-5 text-sm text-gray-800">
            {ticket.acceptanceCriteria.map((criterion, index) => (
              <li key={`${ticket.id}-criterion-${index}`}>{criterion}</li>
            ))}
          </ul>
        </section>

        {ticket.anomalies.length > 0 && (
          <section>
            <div className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2">
              Anomaly Flags
            </div>
            <div className="flex flex-wrap gap-2">
              {ticket.anomalies.map((flag, index) => {
                const flagKey = `${flag.type}-${index}`;
                const isOpen = openFlag === flagKey;
                return (
                  <div key={flagKey} className="relative">
                    <button
                      type="button"
                      onClick={() =>
                        setOpenFlag((current) =>
                          current === flagKey ? "" : flagKey,
                        )
                      }
                      className="inline-flex items-center gap-1.5 rounded border border-gray-300 bg-white px-2.5 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-50 shadow-sm"
                    >
                      <span>{flag.icon}</span> {flag.type}
                    </button>
                    {isOpen && (
                      <div className="absolute left-0 top-8 z-20 w-64 rounded border border-gray-200 bg-white p-3 text-xs text-gray-700 shadow-lg">
                        {flag.details}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {ticket.subtasks && ticket.subtasks.length > 0 && (
          <section>
            <div className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2 border-b border-gray-200 pb-1">
              Subtasks
            </div>
            <table className="min-w-full text-left text-xs">
              <thead className="text-gray-400">
                <tr>
                  <th className="py-2 pr-2 font-normal">TITLE</th>
                  <th className="py-2 px-2 font-normal w-24">ROLE</th>
                  <th className="py-2 px-2 font-normal w-32">EFFORT</th>
                  <th className="py-2 pl-2 font-normal w-16">ORDER</th>
                </tr>
              </thead>
              <tbody className="text-gray-700 font-medium">
                {ticket.subtasks.map((subtask) => (
                  <tr
                    key={subtask.id}
                    className="border-b border-gray-100 last:border-0 hover:bg-gray-50"
                  >
                    <td className="py-2 pr-2">{subtask.title}</td>
                    <td className="py-2 px-2 text-gray-500">{subtask.role}</td>
                    <td className="py-2 px-2">
                      <div className="flex items-center justify-between w-full">
                        <span className="w-10 bg-gray-200 h-1.5 rounded-full inline-block mr-2">
                          <div
                            className="bg-blue-500 h-1.5 rounded-full"
                            style={{
                              width: `${Math.min(100, parseFloat(subtask.effort) * 100)}%`,
                            }}
                          ></div>
                        </span>
                        <span>{subtask.effort}</span>
                      </div>
                    </td>
                    <td className="py-2 pl-2">{subtask.order}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-end gap-2">
        {showUndo && (
          <button
            type="button"
            onClick={onUndoReject}
            className="inline-flex items-center gap-1 rounded bg-white border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <Undo2 className="h-4 w-4" />
            Undo
          </button>
        )}
        <button
          type="button"
          onClick={onReject}
          className="rounded border border-gray-300 bg-white px-4 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Reject
        </button>
        <button
          type="button"
          onClick={onEdit}
          className="rounded border border-gray-300 bg-white px-4 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Edit
        </button>
        <button
          type="button"
          onClick={onAccept}
          className="rounded bg-[#0052CC] px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          Accept &rarr;
        </button>
      </div>
    </article>
  );
}

function EditModal({ ticket, setTicket, onCancel, onSave }) {
  function updateField(field, value) {
    setTicket((current) => ({ ...current, [field]: value }));
  }

  function updateAcceptance(index, value) {
    setTicket((current) => {
      const nextCriteria = [...current.acceptanceCriteria];
      nextCriteria[index] = value;
      return { ...current, acceptanceCriteria: nextCriteria };
    });
  }

  function addAcceptanceCriterion() {
    setTicket((current) => ({
      ...current,
      acceptanceCriteria: [...current.acceptanceCriteria, ""],
    }));
  }

  function removeAcceptance(index) {
    setTicket((current) => ({
      ...current,
      acceptanceCriteria: current.acceptanceCriteria.filter(
        (_, currentIndex) => currentIndex !== index,
      ),
    }));
  }

  function addSubtask() {
    setTicket((current) => ({
      ...current,
      subtasks: [
        ...current.subtasks,
        {
          id: `S-${Date.now()}`,
          title: "New subtask",
          role: "Frontend",
          effort: "0.10",
          order: current.subtasks.length + 1,
        },
      ],
    }));
  }

  function updateSubtask(index, key, value) {
    setTicket((current) => {
      const nextSubtasks = current.subtasks.map((subtask, subtaskIndex) =>
        subtaskIndex === index ? { ...subtask, [key]: value } : subtask,
      );
      return { ...current, subtasks: nextSubtasks };
    });
  }

  function removeSubtask(index) {
    setTicket((current) => ({
      ...current,
      subtasks: current.subtasks.filter(
        (_, subtaskIndex) => subtaskIndex !== index,
      ),
    }));
  }

  function moveSubtask(index, direction) {
    setTicket((current) => {
      const targetIndex = direction === "up" ? index - 1 : index + 1;
      if (targetIndex < 0 || targetIndex >= current.subtasks.length)
        return current;
      const nextSubtasks = [...current.subtasks];
      const [moved] = nextSubtasks.splice(index, 1);
      nextSubtasks.splice(targetIndex, 0, moved);
      return { ...current, subtasks: nextSubtasks };
    });
  }

  return (
    <section className="min-h-[calc(100vh-8rem)] rounded-2xl border border-gray-200 bg-gray-100 p-4 transition-all duration-200 dark:border-gray-700 dark:bg-gray-950 sm:p-6">
      <div className="mx-auto w-full max-w-5xl rounded-2xl border border-gray-200 bg-white p-5 shadow-soft transition-all duration-200 dark:border-gray-700 dark:bg-gray-900">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Edit Ticket
            </p>
            <h3 className="text-xl font-semibold">{ticket.id}</h3>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-gray-300 p-2 transition-all duration-200 hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm font-medium">Title</label>
            <input
              value={ticket.title}
              onChange={(event) => updateField("title", event.target.value)}
              className="w-full rounded-xl border border-gray-300 bg-gray-50 px-3 py-2 outline-none transition-all duration-200 focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950"
            />
          </div>

          <div className="sm:col-span-2">
            <label className="mb-1 block text-sm font-medium">
              Description
            </label>
            <textarea
              rows={4}
              value={ticket.description}
              onChange={(event) =>
                updateField("description", event.target.value)
              }
              className="w-full rounded-xl border border-gray-300 bg-gray-50 px-3 py-2 outline-none transition-all duration-200 focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Priority</label>
            <select
              value={ticket.priority}
              onChange={(event) => updateField("priority", event.target.value)}
              className="w-full rounded-xl border border-gray-300 bg-gray-50 px-3 py-2 outline-none transition-all duration-200 focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950"
            >
              {PRIORITIES.map((priority) => (
                <option
                  key={priority}
                  value={priority}
                  className="text-gray-900"
                >
                  {priority}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">
              Story Point Override
            </label>
            <input
              type="number"
              min={1}
              value={ticket.overrideStoryPoints || ""}
              onChange={(event) =>
                updateField(
                  "overrideStoryPoints",
                  event.target.value ? Number(event.target.value) : null,
                )
              }
              className="w-full rounded-xl border border-gray-300 bg-gray-50 px-3 py-2 outline-none transition-all duration-200 focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950"
            />
          </div>
        </div>

        <div className="mt-5 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-950">
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-sm font-semibold">Acceptance Criteria</h4>
            <button
              type="button"
              onClick={addAcceptanceCriterion}
              className="inline-flex items-center gap-1 rounded-lg border border-indigo-300 px-2 py-1 text-xs font-semibold text-indigo-700 transition-all duration-200 hover:bg-indigo-50 dark:border-indigo-700 dark:text-indigo-300 dark:hover:bg-indigo-900/30"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Item
            </button>
          </div>
          <div className="space-y-2">
            {ticket.acceptanceCriteria.map((criterion, index) => (
              <div
                key={`${ticket.id}-edit-criterion-${index}`}
                className="flex items-center gap-2"
              >
                <input
                  value={criterion}
                  onChange={(event) =>
                    updateAcceptance(index, event.target.value)
                  }
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm outline-none transition-all duration-200 focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-900"
                />
                <button
                  type="button"
                  onClick={() => removeAcceptance(index)}
                  className="rounded-lg border border-red-300 p-1.5 text-red-600 transition-all duration-200 hover:bg-red-50 dark:border-red-700 dark:text-red-300 dark:hover:bg-red-900/30"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-5 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-950">
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-sm font-semibold">Subtasks</h4>
            <button
              type="button"
              onClick={addSubtask}
              className="inline-flex items-center gap-1 rounded-lg border border-indigo-300 px-2 py-1 text-xs font-semibold text-indigo-700 transition-all duration-200 hover:bg-indigo-50 dark:border-indigo-700 dark:text-indigo-300 dark:hover:bg-indigo-900/30"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Subtask
            </button>
          </div>
          <div className="space-y-2">
            {ticket.subtasks.map((subtask, index) => (
              <div
                key={subtask.id}
                className="grid gap-2 rounded-lg border border-gray-200 bg-white p-2 dark:border-gray-700 dark:bg-gray-900 sm:grid-cols-[1.3fr_0.7fr_0.5fr_auto]"
              >
                <input
                  value={subtask.title}
                  onChange={(event) =>
                    updateSubtask(index, "title", event.target.value)
                  }
                  className="rounded-lg border border-gray-300 bg-gray-50 px-2 py-1.5 text-sm outline-none transition-all duration-200 focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950"
                />
                <select
                  value={subtask.role}
                  onChange={(event) =>
                    updateSubtask(index, "role", event.target.value)
                  }
                  className="rounded-lg border border-gray-300 bg-gray-50 px-2 py-1.5 text-sm outline-none transition-all duration-200 focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950"
                >
                  {ROLES.map((role) => (
                    <option key={role} value={role} className="text-gray-900">
                      {role}
                    </option>
                  ))}
                </select>
                <input
                  value={subtask.effort}
                  onChange={(event) =>
                    updateSubtask(index, "effort", event.target.value)
                  }
                  className="rounded-lg border border-gray-300 bg-gray-50 px-2 py-1.5 text-sm outline-none transition-all duration-200 focus:border-indigo-500 dark:border-gray-700 dark:bg-gray-950"
                />
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => moveSubtask(index, "up")}
                    className="rounded border border-gray-300 p-1 transition-all duration-200 hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-800"
                  >
                    <ArrowUp className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => moveSubtask(index, "down")}
                    className="rounded border border-gray-300 p-1 transition-all duration-200 hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-800"
                  >
                    <ArrowDown className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => removeSubtask(index)}
                    className="rounded border border-red-300 p-1 text-red-600 transition-all duration-200 hover:bg-red-50 dark:border-red-700 dark:text-red-300 dark:hover:bg-red-900/30"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium transition-all duration-200 hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-800"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSave}
            className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-all duration-200 hover:bg-indigo-700"
          >
            Save & Accept
          </button>
        </div>
      </div>
    </section>
  );
}

export default App;
