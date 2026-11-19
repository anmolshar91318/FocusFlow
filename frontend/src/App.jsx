import React, { useCallback, useEffect, useMemo, useState } from "react";

const RAW_API_URL =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_BACKEND_URL ||
  "http://localhost:5000/api";
const SANITIZED_URL = RAW_API_URL.replace(/\/+$/, "");
const API = SANITIZED_URL.endsWith("/api") ? SANITIZED_URL : `${SANITIZED_URL}/api`;
const FOCUS_SECONDS = 25 * 60;
const BREAK_SECONDS = 5 * 60;

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

function formatTime(n) {
  return `${Math.floor(n / 60).toString().padStart(2, "0")}:${(n % 60).toString().padStart(2, "0")}`;
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z");
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

const VALID_SECTIONS = new Set([
  "dashboard",
  "progression",
  "tasks",
  "focus",
  "habits",
  "analytics",
  "assistant",
]);

function getInitialSection() {
  try {
    // 1. Check URL hash first (e.g. #tasks or #focus)
    const hash = window.location.hash.replace(/^#\/?/, "").toLowerCase().trim();
    if (VALID_SECTIONS.has(hash)) return hash;

    // 2. Check localStorage
    const saved = localStorage.getItem("focusflow-active-tab");
    if (saved && VALID_SECTIONS.has(saved)) return saved;
  } catch {}
  return "dashboard";
}

function getInitialTimerState() {
  try {
    const raw = localStorage.getItem("focusflow-timer-state");
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const focusMins = Math.max(1, Math.min(180, Number(parsed.focusMinutesSetting) || 25));
    const breakMins = Math.max(1, Math.min(60, Number(parsed.breakMinutesSetting) || 5));
    const mode = parsed.mode === "break" ? "break" : "focus";

    let remaining = Number(parsed.remaining);
    if (isNaN(remaining) || remaining < 0) {
      remaining = (mode === "focus" ? focusMins : breakMins) * 60;
    }

    let running = Boolean(parsed.running);

    if (running && parsed.targetEndTime) {
      const now = Date.now();
      const secondsLeft = Math.round((parsed.targetEndTime - now) / 1000);
      if (secondsLeft > 0) {
        remaining = secondsLeft;
        running = true;
      } else {
        remaining = (mode === "focus" ? focusMins : breakMins) * 60;
        running = false;
      }
    }

    return {
      mode,
      focusMinutesSetting: focusMins,
      breakMinutesSetting: breakMins,
      remaining,
      running,
    };
  } catch {
    return null;
  }
}

function Icon({ name, size = 18 }) {
  const props = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };

  switch (name) {
    case "dashboard":
      return (
        <svg {...props}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "tasks":
      return (
        <svg {...props}>
          <path d="M9 11l3 3L22 4" />
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
        </svg>
      );
    case "focus":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="9" />
          <polyline points="12 7 12 12 15 15" />
        </svg>
      );
    case "habits":
      return (
        <svg {...props}>
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
        </svg>
      );
    case "analytics":
      return (
        <svg {...props}>
          <line x1="18" y1="20" x2="18" y2="10" />
          <line x1="12" y1="20" x2="12" y2="4" />
          <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
      );
    case "assistant":
      return (
        <svg {...props}>
          <path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z" />
        </svg>
      );
    case "award":
      return (
        <svg {...props}>
          <circle cx="12" cy="8" r="7" />
          <polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88" />
        </svg>
      );
    case "trophy":
      return (
        <svg {...props}>
          <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
          <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
          <path d="M4 22h16" />
          <path d="M10 14.66V17c0 .55-.45 1-1 1H7c-.55 0-1 .45-1 1v1c0 .55.45 1 1 1h10c.55 0 1-.45 1-1v-1c0-.55-.45-1-1-1h-2c-.55 0-1-.45-1-1v-2.34" />
          <path d="M18 4H6v5a6 6 0 0 0 12 0V4z" />
        </svg>
      );
    case "crown":
      return (
        <svg {...props}>
          <path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7zm3 16h14v2H5v-2z" />
        </svg>
      );
    case "zap":
      return (
        <svg {...props}>
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
        </svg>
      );
    case "target":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="10" />
          <circle cx="12" cy="12" r="6" />
          <circle cx="12" cy="12" r="2" />
        </svg>
      );
    case "brain":
      return (
        <svg {...props}>
          <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-5.04z" />
          <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-5.04z" />
        </svg>
      );
    case "sunrise":
      return (
        <svg {...props}>
          <path d="M12 2v4M4.93 10.93l1.41 1.41M2 18h2M20 18h2M17.66 12.34l1.41-1.41M16 18a4 4 0 0 0-8 0" />
          <line x1="2" y1="22" x2="22" y2="22" />
        </svg>
      );
    case "checkCircle":
      return (
        <svg {...props}>
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
          <polyline points="22 4 12 14.01 9 11.01" />
        </svg>
      );
    case "lock":
      return (
        <svg {...props}>
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      );
    case "sun":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
        </svg>
      );
    case "moon":
      return (
        <svg {...props}>
          <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
        </svg>
      );
    case "plus":
      return (
        <svg {...props}>
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
      );
    case "check":
      return (
        <svg {...props}>
          <polyline points="20 6 9 17 4 12" />
        </svg>
      );
    case "edit":
      return (
        <svg {...props}>
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
        </svg>
      );
    case "trash":
      return (
        <svg {...props}>
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
      );
    case "play":
      return (
        <svg {...props}>
          <polygon points="5 3 19 12 5 21 5 3" />
        </svg>
      );
    case "pause":
      return (
        <svg {...props}>
          <rect x="6" y="4" width="4" height="16" />
          <rect x="14" y="4" width="4" height="16" />
        </svg>
      );
    case "reset":
      return (
        <svg {...props}>
          <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
          <path d="M3 3v5h5" />
        </svg>
      );
    case "trend":
      return (
        <svg {...props}>
          <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
          <polyline points="17 6 23 6 23 12" />
        </svg>
      );
    case "flame":
      return (
        <svg {...props}>
          <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
        </svg>
      );
    case "logout":
      return (
        <svg {...props}>
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
          <polyline points="16 17 21 12 16 7" />
          <line x1="21" y1="12" x2="9" y2="12" />
        </svg>
      );
    case "arrowRight":
      return (
        <svg {...props}>
          <line x1="5" y1="12" x2="19" y2="12" />
          <polyline points="12 5 19 12 12 19" />
        </svg>
      );
    case "sparkle":
      return (
        <svg {...props}>
          <path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z" />
        </svg>
      );
    case "send":
      return (
        <svg {...props}>
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      );
    case "settings":
      return (
        <svg {...props}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      );
    case "key":
      return (
        <svg {...props}>
          <path d="M21 2l-2 2m-1.5 1.5L14 9l-1.5-1.5L11 9l1.5 1.5L9 14a5 5 0 1 1-7-7 5 5 0 0 1 7 7l3.5-3.5L14 12l1.5-1.5L14 9l3.5-3.5M21 2l-2 2" />
        </svg>
      );
    case "chevronDown":
      return (
        <svg {...props}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      );
    default:
      return null;
  }
}

export default function App() {
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [authName, setAuthName] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [activeSection, setActiveSection] = useState(() => getInitialSection());
  const [tasks, setTasks] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [progression, setProgression] = useState(null);
  const [toasts, setToasts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("Study");
  const [priority, setPriority] = useState("Medium");
  const [dueDate, setDueDate] = useState("");
  const [estimate, setEstimate] = useState("30");
  const [editingTaskId, setEditingTaskId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");

  const initialTimer = useMemo(() => getInitialTimerState(), []);

  const [mode, setMode] = useState(() => initialTimer?.mode || "focus");
  const [focusMinutesSetting, setFocusMinutesSetting] = useState(
    () => initialTimer?.focusMinutesSetting || 25
  );
  const [breakMinutesSetting, setBreakMinutesSetting] = useState(
    () => initialTimer?.breakMinutesSetting || 5
  );
  const [remaining, setRemaining] = useState(
    () => (initialTimer?.remaining !== undefined ? initialTimer.remaining : FOCUS_SECONDS)
  );
  const [running, setRunning] = useState(() => initialTimer?.running || false);

  const [nightMode, setNightMode] = useState(() => localStorage.getItem("focusflow-theme") === "night");
  const [taskFilter, setTaskFilter] = useState("All");
  const [priorityFilter, setPriorityFilter] = useState("All");

  const [habitName, setHabitName] = useState("");
  const [habits, setHabits] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(`ff-habits-${user?.id || user?.email || "guest"}`) || "[]");
    } catch {
      return [];
    }
  });
  const todayKey = new Date().toISOString().slice(0, 10);

  const addToast = useCallback((toast) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { ...toast, id }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  useEffect(() => {
    if (user) {
      localStorage.setItem(`ff-habits-${user.id || user.email}`, JSON.stringify(habits));
    }
  }, [habits, user]);

  useEffect(() => {
    localStorage.setItem("focusflow-theme", nightMode ? "night" : "day");
  }, [nightMode]);

  useEffect(() => {
    try {
      const timerState = {
        mode,
        focusMinutesSetting,
        breakMinutesSetting,
        remaining,
        running,
        targetEndTime: running ? Date.now() + remaining * 1000 : null,
      };
      localStorage.setItem("focusflow-timer-state", JSON.stringify(timerState));
    } catch {}
  }, [mode, focusMinutesSetting, breakMinutesSetting, remaining, running]);

  useEffect(() => {
    api("/auth/me")
      .then((data) => setUser(data.user))
      .catch(() => setUser(null))
      .finally(() => setAuthChecked(true));
  }, []);

  const refresh = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      setError("");
      const [t, s, p] = await Promise.all([
        api("/tasks"),
        api("/sessions"),
        api("/progression").catch(() => ({ progression: null })),
      ]);
      setTasks(t.tasks || []);
      setSessions(s.sessions || []);
      if (p && p.progression) {
        setProgression(p.progression);
      } else {
        // Resilient fallback progression if server response is null or delayed
        const doneCount = (t?.tasks || []).filter((task) => task.completed).length;
        const focusMins = (s?.sessions || []).reduce((acc, sess) => acc + (Number(sess.duration_minutes) || 0), 0);
        const estXp = doneCount * 10 + focusMins;
        const level = estXp >= 700 ? 5 : estXp >= 450 ? 4 : estXp >= 250 ? 3 : estXp >= 100 ? 2 : 1;
        const nextXp = level === 1 ? 100 : level === 2 ? 250 : level === 3 ? 450 : 700;
        const curBase = level === 1 ? 0 : level === 2 ? 100 : level === 3 ? 250 : 450;
        const curLvlXp = estXp - curBase;
        const pct = Math.min(100, Math.max(0, Math.round((curLvlXp / (nextXp - curBase)) * 100)));
        setProgression((prev) => prev || {
          current_level: level,
          level_title: level >= 5 ? "Productivity Enthusiast" : level >= 3 ? "Focus Explorer" : level >= 2 ? "Getting Started" : "Beginner",
          rank_tier: estXp >= 1000 ? "Silver" : "Bronze",
          rank_badge: estXp >= 1000 ? "silver" : "bronze",
          rank_description: "Foundation of Focus",
          current_level_xp: curLvlXp,
          next_level_xp: nextXp - curBase,
          total_xp: estXp,
          progress_percent: pct,
          total_focus_hours: Math.round((focusMins / 60) * 10) / 10,
          total_sessions: (s?.sessions || []).length,
          completed_tasks: doneCount,
          current_streak: 0,
          weekly_xp: estXp,
          unlocked_achievements_count: 0,
          total_achievements_count: 12,
          achievements: [],
          recent_activity: [],
        });
      }
    } catch (e) {
      setError(`${e.message} Please check that the backend is running.`);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      refresh();
      try {
        const saved = localStorage.getItem(`ff-habits-${user.id || user.email}`);
        if (saved) setHabits(JSON.parse(saved));
      } catch { }
    } else {
      setTasks([]);
      setSessions([]);
      setProgression(null);
    }
  }, [user, refresh]);

  // Persist active section across page refreshes and synchronize with URL hash
  useEffect(() => {
    try {
      localStorage.setItem("focusflow-active-tab", activeSection);
      if (window.location.hash !== `#${activeSection}`) {
        window.history.replaceState(null, "", `#${activeSection}`);
      }
    } catch { }
  }, [activeSection]);

  useEffect(() => {
    function handleHashChange() {
      const hash = window.location.hash.replace(/^#\/?/, "").toLowerCase().trim();
      if (VALID_SECTIONS.has(hash)) {
        setActiveSection(hash);
      }
    }
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  async function submitAuth(e) {
    e.preventDefault();
    setAuthBusy(true);
    setAuthError("");
    try {
      const path = authMode === "register" ? "/auth/register" : "/auth/login";
      const body =
        authMode === "register"
          ? { name: authName, email: authEmail, password: authPassword }
          : { email: authEmail, password: authPassword };
      const data = await api(path, { method: "POST", body: JSON.stringify(body) });
      setUser(data.user);
      setAuthPassword("");
      setProfileOpen(false);
    } catch (e) {
      setAuthError(e.message);
    } finally {
      setAuthBusy(false);
    }
  }

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch (e) {
      setError(e.message);
    }
    setUser(null);
    setTasks([]);
    setSessions([]);
    setProgression(null);
    setRunning(false);
    setProfileOpen(false);
    setProfileModalOpen(false);
    try {
      localStorage.removeItem("focusflow-timer-state");
      localStorage.removeItem("focusflow-active-tab");
      window.history.replaceState(null, "", "#dashboard");
    } catch {}
    setActiveSection("dashboard");
    setMode("focus");
    setFocusMinutesSetting(25);
    setBreakMinutesSetting(5);
    setRemaining(FOCUS_SECONDS);
  }

  // Timer countdown and completion effect with XP & Progression integration
  useEffect(() => {
    if (!running || !user) return;
    const id = window.setInterval(() => {
      setRemaining((n) => {
        if (n > 1) return n - 1;
        window.clearInterval(id);
        setRunning(false);
        if (mode === "focus") {
          api("/sessions", {
            method: "POST",
            body: JSON.stringify({ duration_minutes: focusMinutesSetting }),
          })
            .then((data) => {
              if (data.progression) setProgression(data.progression);
              refresh();

              if (data.xp_earned > 0) {
                addToast({
                  type: "xp",
                  title: "Focus Block Completed!",
                  message: `Earned +${data.xp_earned} XP for ${focusMinutesSetting} minutes of dedicated work.`,
                  xp: data.xp_earned,
                  icon: "focus",
                });
              }

              if (data.streak_bonus > 0) {
                addToast({
                  type: "streak",
                  title: "Daily Streak Active!",
                  message: `Productivity streak maintained (+${data.streak_bonus} XP).`,
                  xp: data.streak_bonus,
                  icon: "flame",
                });
              }

              if (data.weekly_bonus > 0) {
                addToast({
                  type: "weekly",
                  title: "Weekly Focus Goal Reached!",
                  message: `Surpassed 2 hours of focus this week (+${data.weekly_bonus} XP)!`,
                  xp: data.weekly_bonus,
                  icon: "trophy",
                });
              }

              if (data.leveled_up) {
                addToast({
                  type: "level",
                  title: "Level Up!",
                  message: `Congratulations! You reached Level ${data.new_level}: ${data.new_title}`,
                  icon: "award",
                });
              }

              if (data.newly_unlocked_achievements && data.newly_unlocked_achievements.length > 0) {
                data.newly_unlocked_achievements.forEach((ach) => {
                  addToast({
                    type: "achievement",
                    title: "Achievement Unlocked!",
                    message: `${ach.name}: ${ach.description} (+${ach.xp_reward} XP)`,
                    icon: ach.icon || "award",
                  });
                });
              }
            })
            .catch((e) => setError(e.message));

          setMode("break");
          return breakMinutesSetting * 60;
        }

        addToast({
          type: "xp",
          title: "Break Complete!",
          message: "Ready for another high-impact focus session?",
          icon: "sun",
        });
        setMode("focus");
        return focusMinutesSetting * 60;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [running, mode, refresh, user, focusMinutesSetting, breakMinutesSetting, addToast]);

  const done = tasks.filter((t) => t.completed).length;
  const focusMinutes = sessions.reduce((sum, s) => sum + s.duration_minutes, 0);

  async function addTask(e) {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      const data = await api("/tasks", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim(),
          category,
          priority,
          due_date: dueDate,
          estimated_minutes: Number(estimate) || 30,
        }),
      });
      setTasks((prev) => [data.task, ...prev]);
      setTitle("");
      setDueDate("");
      setEstimate("30");
    } catch (e) {
      setError(e.message);
    }
  }

  async function toggle(task) {
    try {
      const data = await api(`/tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({ completed: !task.completed }),
      });
      setTasks((prev) => prev.map((t) => (t.id === task.id ? data.task : t)));

      if (data.progression) setProgression(data.progression);

      if (data.xp_earned > 0) {
        addToast({
          type: "xp",
          title: "Task Completed!",
          message: `Earned +${data.xp_earned} XP for finishing “${task.title.slice(0, 36)}”.`,
          xp: data.xp_earned,
          icon: "check",
        });
      }

      if (data.streak_bonus > 0) {
        addToast({
          type: "streak",
          title: "Daily Streak Active!",
          message: `Productivity streak recorded (+${data.streak_bonus} XP).`,
          xp: data.streak_bonus,
          icon: "flame",
        });
      }

      if (data.leveled_up) {
        addToast({
          type: "level",
          title: "Level Up!",
          message: `Level ${data.new_level}: ${data.new_title}!`,
          icon: "award",
        });
      }

      if (data.newly_unlocked_achievements && data.newly_unlocked_achievements.length > 0) {
        data.newly_unlocked_achievements.forEach((ach) => {
          addToast({
            type: "achievement",
            title: "Achievement Unlocked!",
            message: `${ach.name}: ${ach.description} (+${ach.xp_reward} XP)`,
            icon: ach.icon || "award",
          });
        });
      }
    } catch (e) {
      setError(e.message);
    }
  }

  async function saveTaskEdit(task) {
    const trimmed = editingTitle.trim();
    if (!trimmed || trimmed === task.title) {
      setEditingTaskId(null);
      return;
    }
    try {
      const data = await api(`/tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: trimmed }),
      });
      setTasks((v) => v.map((t) => (t.id === task.id ? data.task : t)));
      setEditingTaskId(null);
    } catch (e) {
      setError(e.message);
      setEditingTaskId(null);
    }
  }

  async function removeTask(id) {
    try {
      await api(`/tasks/${id}`, { method: "DELETE" });
      setTasks((prev) => prev.filter((t) => t.id !== id));
    } catch (e) {
      setError(e.message);
    }
  }

  function addHabit(e) {
    e.preventDefault();
    if (!habitName.trim()) return;
    setHabits((v) => [
      ...v,
      { id: Date.now(), name: habitName.trim(), createdAt: todayKey, completedDates: [] },
    ]);
    setHabitName("");
  }

  function toggleHabit(h) {
    setHabits((v) =>
      v.map((x) =>
        x.id === h.id
          ? {
            ...x,
            completedDates: (x.completedDates || []).includes(todayKey)
              ? x.completedDates.filter((d) => d !== todayKey)
              : [...(x.completedDates || []), todayKey],
          }
          : x
      )
    );
  }

  function removeHabit(id) {
    setHabits((v) => v.filter((h) => h.id !== id));
  }

  function setTimerMode(next) {
    setRunning(false);
    setMode(next);
    setRemaining((next === "focus" ? focusMinutesSetting : breakMinutesSetting) * 60);
  }

  const pendingTasks = tasks.filter((t) => !t.completed);
  const completionRate = tasks.length ? Math.round((done / tasks.length) * 100) : 0;
  const todayHabits = habits.filter((h) => (h.completedDates || []).includes(todayKey)).length;
  const habitConsistency = habits.length ? Math.round((todayHabits / habits.length) * 100) : 0;

  const filteredTasks = tasks
    .filter((t) =>
      taskFilter === "All" ? true : taskFilter === "Completed" ? t.completed : !t.completed
    )
    .filter((t) => priorityFilter === "All" || t.priority === priorityFilter);

  const suggestionText = useMemo(() => {
    if (!pendingTasks.length) {
      return "Your task list is clear. Add your next important task or use this time to plan tomorrow.";
    }
    const rank = { High: 0, Medium: 1, Low: 2 };
    const sorted = [...pendingTasks].sort((a, b) => {
      const ad = a.due_date && a.due_date <= todayKey ? 0 : 1;
      const bd = b.due_date && b.due_date <= todayKey ? 0 : 1;
      return (
        ad - bd ||
        rank[a.priority] - rank[b.priority] ||
        (a.estimated_minutes || 30) - (b.estimated_minutes || 30)
      );
    });
    const t = sorted[0];
    return `Start with “${t.title}”. It is ${t.priority.toLowerCase()} priority${t.due_date ? ` and is due ${t.due_date}` : ""
      }. Consider one ${Math.min(Number(t.estimated_minutes) || 30, 25)}-minute focus block, then review your progress.`;
  }, [pendingTasks, todayKey]);

  const totalSeconds = (mode === "focus" ? focusMinutesSetting : breakMinutesSetting) * 60;
  const timerProgress = totalSeconds > 0 ? ((totalSeconds - remaining) / totalSeconds) * 100 : 0;
  const circleRadius = 104;
  const circleCircumference = 2 * Math.PI * circleRadius;
  const strokeDashoffset = circleCircumference - (timerProgress / 100) * circleCircumference;

  if (!authChecked) {
    return (
      <div className={`auth-shell ${nightMode ? "dark" : ""}`}>
        <div className="auth-card auth-loading">
          <div className="auth-logo">F</div>
          <p className="eyebrow">FOCUSFLOW</p>
          <h1>Getting your study space ready…</h1>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className={`auth-shell ${nightMode ? "dark" : ""}`}>
        <div className="auth-decoration decor-one" />
        <div className="auth-decoration decor-two" />
        <section className="auth-card">
          <div className="auth-brand">
            <span className="logo">F</span>
            <span>FocusFlow</span>
          </div>
          <p className="eyebrow">YOUR PERSONAL STUDY SPACE</p>
          <h1>{authMode === "login" ? "Welcome back." : "Create your space."}</h1>
          <p className="auth-subtitle">
            {authMode === "login"
              ? "Sign in and pick up where your focus left off."
              : "A calmer way to plan, focus, and make progress."}
          </p>
          <div className="auth-tabs">
            <button
              type="button"
              className={authMode === "login" ? "active" : ""}
              onClick={() => {
                setAuthMode("login");
                setAuthError("");
              }}
            >
              Log in
            </button>
            <button
              type="button"
              className={authMode === "register" ? "active" : ""}
              onClick={() => {
                setAuthMode("register");
                setAuthError("");
              }}
            >
              Create account
            </button>
          </div>
          <form className="auth-form" onSubmit={submitAuth}>
            {authMode === "register" && (
              <label>
                Your name
                <input
                  value={authName}
                  onChange={(e) => setAuthName(e.target.value)}
                  placeholder="e.g. Anmol"
                  autoComplete="name"
                  required
                  minLength={2}
                  maxLength={60}
                />
              </label>
            )}
            <label>
              Email address
              <input
                type="email"
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete={authMode === "login" ? "current-password" : "new-password"}
                required
                minLength={8}
              />
            </label>
            {authError && <div className="error">{authError}</div>}
            <button className="primary auth-submit" disabled={authBusy}>
              {authBusy
                ? "Please wait…"
                : authMode === "login"
                  ? "Log in to FocusFlow"
                  : "Create my account"}
              <Icon name="arrowRight" size={16} />
            </button>
          </form>
          <p className="auth-foot">Your tasks, focus sessions, and achievements are saved securely.</p>
          <button
            type="button"
            className="auth-theme"
            onClick={() => setNightMode((v) => !v)}
            aria-label="Toggle day and night mode"
          >
            <Icon name={nightMode ? "moon" : "sun"} size={14} />
            <span>{nightMode ? "Night mode" : "Day mode"}</span>
          </button>
        </section>

        <aside className="auth-aside">
          <div className="auth-aside-mark">
            <Icon name="assistant" size={26} />
          </div>
          <p className="eyebrow">PRODUCTIVITY PROGRESSION</p>
          <h2>Turn disciplined effort into lasting mastery.</h2>
          <p>
            Earn XP for focused work, unlock achievements, climb prestige ranks, and build genuine
            study consistency.
          </p>
          <div className="auth-quote">
            “Success is the sum of small efforts, repeated day in and day out.”
          </div>
        </aside>
      </div>
    );
  }

  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: "dashboard" },
    { id: "progression", label: "Progression & Badges", icon: "award" },
    { id: "tasks", label: "Task management", icon: "tasks" },
    { id: "focus", label: "Focus timer", icon: "focus" },
    { id: "habits", label: "Habit tracker", icon: "habits" },
    { id: "analytics", label: "Analytics & reports", icon: "analytics" },
    { id: "assistant", label: "AI assistant", icon: "assistant" },
  ];

  const pageMeta = {
    dashboard: ["Dashboard", "Your productivity overview, daily progression, and priorities."],
    progression: ["Progression & Rewards", "Level up, achieve ranks, and earn badges through genuine deep work."],
    tasks: ["Task management", "Plan, prioritize, and keep every commitment organized."],
    focus: ["Focus timer", "Protect your attention with structured work and break sessions."],
    habits: ["Habit tracker", "Build consistency through small, repeatable daily actions."],
    analytics: ["Analytics & reports", "Understand your completion trends and focus patterns."],
    assistant: ["AI productivity assistant", "Practical, transparent suggestions based on your workload."],
  };

  return (
    <div className={`layout ff-layout ${nightMode ? "dark" : ""}`} data-theme={nightMode ? "night" : "day"}>
      {/* Toast Notification Layer */}
      <ToastNotification toasts={toasts} onDismiss={dismissToast} />

      {/* Profile Modal Dialog */}
      {profileModalOpen && (
        <ProfileModal
          user={user}
          progression={progression}
          onClose={() => setProfileModalOpen(false)}
          onLogout={logout}
        />
      )}

      <aside className="sidebar">
        <a
          className="brand"
          href="#dashboard"
          onClick={(e) => {
            e.preventDefault();
            setActiveSection("dashboard");
          }}
        >
          <span className="logo">F</span>
          <span>FocusFlow</span>
        </a>

        <p className="side-label">WORKSPACE</p>
        <nav>
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav ${activeSection === item.id ? "active" : ""}`}
              onClick={() => setActiveSection(item.id)}
            >
              <span className="nav-icon">
                <Icon name={item.icon} size={17} />
              </span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        {progression && (
          <div
            className="side-note"
            style={{ cursor: "pointer" }}
            onClick={() => setActiveSection("progression")}
            title="Click to view full progression"
          >
            <div className="side-note-icon">
              <Icon name="award" size={16} />
            </div>
            <b>Level {progression.current_level} · {progression.rank_tier}</b>
            <p>{progression.level_title} ({progression.total_xp} XP)</p>
          </div>
        )}

        <div className="side-footer">
          <span>MCA MINOR PROJECT</span>
          <b>Smart Productivity System</b>
        </div>
      </aside>

      <main className={`main ff-main ${activeSection === "assistant" ? "assistant-mode" : ""}`}>
        <header className={`header ${activeSection === "assistant" ? "header-minimal" : ""}`}>
          {activeSection !== "assistant" && (
            <div className="header-title">
              <p className="eyebrow">FOCUSFLOW WORKSPACE</p>
              <h1>
                {pageMeta[activeSection][0]}
                <span>.</span>
              </h1>
              <p className="muted">{pageMeta[activeSection][1]}</p>
            </div>
          )}

          <div className="header-actions">
            <button
              className={`mode-switch ${nightMode ? "on" : ""}`}
              onClick={() => setNightMode((v) => !v)}
              role="switch"
              aria-checked={nightMode}
              aria-label="Toggle day and night mode"
              title={nightMode ? "Switch to Day Mode" : "Switch to Night Mode"}
            >
              <span className="switch-sun">
                <Icon name="sun" size={14} />
              </span>
              <span className="switch-moon">
                <Icon name="moon" size={14} />
              </span>
              <span className="switch-knob" />
            </button>

            <div className="profile-wrap">
              <button
                className="profile-button"
                onClick={() => setProfileOpen((v) => !v)}
                aria-expanded={profileOpen}
              >
                <span className="avatar">{user.name.trim().charAt(0).toUpperCase()}</span>
                <span className="profile-name">{user.name}</span>
                {progression && (
                  <span className={`rank-chip rank-${progression.rank_badge || "bronze"}`}>
                    Lv {progression.current_level}
                  </span>
                )}
                <span className={`profile-chevron ${profileOpen ? "open" : ""}`}>
                  <Icon name="chevronDown" size={13} />
                </span>
              </button>
              {profileOpen && (
                <div className="profile-menu">
                  <div className="profile-menu-info">
                    <b>{user.name}</b>
                    <small>{user.email}</small>
                    {progression && (
                      <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 6 }}>
                        <span className={`rank-chip rank-${progression.rank_badge || "bronze"}`}>
                          {progression.rank_tier} Tier
                        </span>
                        <span className="level-chip">Level {progression.current_level}</span>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => {
                      setProfileOpen(false);
                      setProfileModalOpen(true);
                    }}
                    style={{ color: "var(--accent)", borderBottom: "1px solid var(--border-subtle)", borderRadius: 0, paddingBottom: 10, marginBottom: 6 }}
                  >
                    <Icon name="award" size={15} />
                    <span>View Profile & Progression</span>
                  </button>
                  <button onClick={logout}>
                    <Icon name="logout" size={15} />
                    <span>Log out</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {error && (
          <div className="error">
            <span>{error}</span>
            <button onClick={() => setError("")} aria-label="Dismiss error">
              ×
            </button>
          </div>
        )}

        {loading && (
          <div className="loading-banner">
            <span className="pulse-dot" />
            <span>Syncing your workspace…</span>
          </div>
        )}

        {activeSection === "dashboard" && (
          <div className="page-content">
            <section className="welcome-strip">
              <div className="welcome-copy">
                <span className="date-pill">
                  {new Date().toLocaleDateString(undefined, {
                    weekday: "long",
                    month: "long",
                    day: "numeric",
                  })}
                </span>
                <h2>Welcome back, {user.name.split(" ")[0]}.</h2>
                <p>Choose one meaningful task and give it your undivided attention.</p>
              </div>
              <button className="primary btn-with-icon" onClick={() => setActiveSection("tasks")}>
                <Icon name="plus" size={16} />
                <span>Add a new task</span>
              </button>
            </section>

            {/* Dashboard Productivity Progression Widget */}
            <DashboardProgressionWidget
              progression={progression}
              onOpenProgression={() => setActiveSection("progression")}
            />

            <section className="stats">
              <Stat label="Total tasks" value={tasks.length} detail="In your workspace" icon="tasks" tone="purple" />
              <Stat label="Completed" value={done} detail={`${pendingTasks.length} still pending`} icon="check" tone="green" />
              <Stat label="Focus minutes" value={focusMinutes} detail={`${sessions.length} recorded sessions`} icon="focus" tone="orange" />
              <Stat label="Completion rate" value={`${completionRate}%`} detail="Overall task progress" icon="trend" tone="blue" />
            </section>

            <section className="dashboard-grid">
              <div className="panel">
                <div className="panel-head">
                  <div>
                    <p className="eyebrow">YOUR NEXT ACTIONS</p>
                    <h2>Pending tasks</h2>
                  </div>
                  <button className="text-link btn-with-icon" onClick={() => setActiveSection("tasks")}>
                    <span>Manage all</span>
                    <Icon name="arrowRight" size={14} />
                  </button>
                </div>

                {!pendingTasks.length ? (
                  <div className="empty">
                    <div className="empty-icon">
                      <Icon name="check" size={22} />
                    </div>
                    <b>You're all caught up</b>
                    <p>Add a task whenever you're ready to plan your next study block.</p>
                  </div>
                ) : (
                  <div className="task-list">
                    {pendingTasks.slice(0, 5).map((t) => (
                      <article className="task-card-row" key={t.id}>
                        <button
                          className={`check ${t.completed ? "checked" : ""}`}
                          onClick={() => toggle(t)}
                          aria-label="Complete task"
                        >
                          {t.completed && <Icon name="check" size={13} />}
                        </button>
                        <div className="task-copy">
                          <b>{t.title}</b>
                          <div className="task-meta">
                            <span className="meta-chip">{t.category}</span>
                            <span>{t.estimated_minutes} min</span>
                            {t.due_date && <span>Due {t.due_date}</span>}
                            <span className="ach-xp-tag">+10 XP</span>
                          </div>
                        </div>
                        <span className={`priority ${(t.priority || "Medium").toLowerCase()}`}>
                          {t.priority}
                        </span>
                      </article>
                    ))}
                  </div>
                )}
              </div>

              <div className="panel dashboard-progress">
                <div className="panel-head">
                  <div>
                    <p className="eyebrow">DAILY SNAPSHOT</p>
                    <h2>Today's progress</h2>
                  </div>
                </div>

                <div className="snapshot-box">
                  <div className="snapshot-header">
                    <span className="progress-number">{completionRate}%</span>
                    <span className="muted">
                      {done} of {tasks.length} done
                    </span>
                  </div>
                  <div className="progress-track">
                    <span style={{ width: `${completionRate}%` }} />
                  </div>
                </div>

                <div className="quick-links">
                  <button onClick={() => setActiveSection("focus")}>
                    <span className="ql-icon orange">
                      <Icon name="focus" size={16} />
                    </span>
                    <span>Start a focus session (+25 XP)</span>
                  </button>
                  <button onClick={() => setActiveSection("progression")}>
                    <span className="ql-icon purple">
                      <Icon name="award" size={16} />
                    </span>
                    <span>
                      Progression & Badges ({progression?.unlocked_achievements_count || 0}/
                      {progression?.total_achievements_count || 12})
                    </span>
                  </button>
                  <button onClick={() => setActiveSection("habits")}>
                    <span className="ql-icon purple">
                      <Icon name="habits" size={16} />
                    </span>
                    <span>Check daily habits ({todayHabits}/{habits.length})</span>
                  </button>
                  <button onClick={() => setActiveSection("analytics")}>
                    <span className="ql-icon blue">
                      <Icon name="analytics" size={16} />
                    </span>
                    <span>View productivity reports</span>
                  </button>
                </div>
              </div>
            </section>
          </div>
        )}

        {/* Dedicated Progression & Badges Section */}
        {activeSection === "progression" && (
          <div className="page-content">
            <ProgressionSection
              user={user}
              progression={progression}
              onOpenProfileModal={() => setProfileModalOpen(true)}
            />
          </div>
        )}

        {activeSection === "tasks" && (
          <div className="page-content">
            <section className="panel section-panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">PLAN YOUR WORK</p>
                  <h2>Create a new task</h2>
                  <p className="muted">Capture tasks, assign priorities, and earn +10 XP upon completion.</p>
                </div>
                <span className="badge">{pendingTasks.length} pending</span>
              </div>

              <form className="task-form" onSubmit={addTask}>
                <label className="wide">
                  Task title
                  <input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Complete system architecture documentation"
                    maxLength="120"
                    required
                  />
                </label>
                <label>
                  Category
                  <select value={category} onChange={(e) => setCategory(e.target.value)}>
                    {["Study", "Assignment", "Exam preparation", "Personal", "Project"].map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Priority
                  <select value={priority} onChange={(e) => setPriority(e.target.value)}>
                    {["High", "Medium", "Low"].map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Due date
                  <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
                </label>
                <label>
                  Estimated minutes
                  <input
                    type="number"
                    min="1"
                    max="1440"
                    value={estimate}
                    onChange={(e) => setEstimate(e.target.value)}
                  />
                </label>
                <button className="primary wide btn-with-icon center" type="submit">
                  <Icon name="plus" size={16} />
                  <span>Add task to workspace</span>
                </button>
              </form>
            </section>

            <section className="panel section-panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">YOUR TASK LIST</p>
                  <h2>Manage tasks</h2>
                </div>
                <div className="filter-row">
                  <select value={taskFilter} onChange={(e) => setTaskFilter(e.target.value)}>
                    <option value="All">Status: All</option>
                    <option value="Pending">Status: Pending</option>
                    <option value="Completed">Status: Completed</option>
                  </select>
                  <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
                    <option value="All">Priority: All</option>
                    <option value="High">High Priority</option>
                    <option value="Medium">Medium Priority</option>
                    <option value="Low">Low Priority</option>
                  </select>
                  <span className="count-pill">{filteredTasks.length} shown</span>
                </div>
              </div>

              <div className="task-list">
                {!filteredTasks.length ? (
                  <div className="empty">
                    <div className="empty-icon">
                      <Icon name="tasks" size={22} />
                    </div>
                    <b>No matching tasks found</b>
                    <p>Create a task above or adjust your active filters.</p>
                  </div>
                ) : (
                  filteredTasks.map((t) => (
                    <article className={`task-card-row ${t.completed ? "is-done" : ""}`} key={t.id}>
                      <button
                        className={`check ${t.completed ? "checked" : ""}`}
                        onClick={() => toggle(t)}
                        aria-label="Toggle task"
                        title={t.completed ? "Mark pending" : "Complete task (+10 XP)"}
                      >
                        {t.completed && <Icon name="check" size={13} />}
                      </button>

                      <div className="task-copy">
                        {editingTaskId === t.id ? (
                          <div className="inline-edit-row">
                            <input
                              value={editingTitle}
                              onChange={(e) => setEditingTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") saveTaskEdit(t);
                                if (e.key === "Escape") setEditingTaskId(null);
                              }}
                              autoFocus
                            />
                            <button className="primary sm" onClick={() => saveTaskEdit(t)}>
                              Save
                            </button>
                            <button className="secondary sm" onClick={() => setEditingTaskId(null)}>
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <>
                            <b>{t.title}</b>
                            <div className="task-meta">
                              <span className="meta-chip">{t.category}</span>
                              <span>{t.estimated_minutes} min</span>
                              {t.due_date && <span>Due {t.due_date}</span>}
                              {!t.completed && <span className="ach-xp-tag">+10 XP</span>}
                            </div>
                          </>
                        )}
                      </div>

                      <span className={`priority ${(t.priority || "Medium").toLowerCase()}`}>
                        {t.priority}
                      </span>

                      <div className="task-actions">
                        <button
                          className="icon-action"
                          onClick={() => {
                            setEditingTaskId(t.id);
                            setEditingTitle(t.title);
                          }}
                          title="Edit task title"
                        >
                          <Icon name="edit" size={14} />
                        </button>
                        <button
                          className="icon-action danger"
                          onClick={() => removeTask(t.id)}
                          title="Delete task"
                        >
                          <Icon name="trash" size={14} />
                        </button>
                      </div>
                    </article>
                  ))
                )}
              </div>
            </section>
          </div>
        )}

        {activeSection === "focus" && (
          <div className="page-content focus-grid">
            <section className="panel timer-page">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">DEEP WORK REWARDS</p>
                  <h2>Pomodoro timer</h2>
                </div>
                <span className="badge">
                  {mode === "focus"
                    ? `Focus Mode (+${focusMinutesSetting} XP)`
                    : "Rest Mode"}
                </span>
              </div>

              <div className="tabs timer-tabs">
                <button className={mode === "focus" ? "selected" : ""} onClick={() => setTimerMode("focus")}>
                  Focus ({focusMinutesSetting}m)
                </button>
                <button className={mode === "break" ? "selected" : ""} onClick={() => setTimerMode("break")}>
                  Short Break ({breakMinutesSetting}m)
                </button>
              </div>

              <div className="svg-ring-wrap">
                <svg className="svg-ring" width="240" height="240" viewBox="0 0 240 240">
                  <circle className="svg-ring-bg" cx="120" cy="120" r={circleRadius} strokeWidth="12" fill="none" />
                  <circle
                    className={`svg-ring-progress ${mode}`}
                    cx="120"
                    cy="120"
                    r={circleRadius}
                    strokeWidth="12"
                    fill="none"
                    strokeDasharray={circleCircumference}
                    strokeDashoffset={strokeDashoffset}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="ring-center-copy">
                  <small>{mode === "focus" ? "FOCUS SESSION" : "SHORT BREAK"}</small>
                  <strong>{formatTime(remaining)}</strong>
                  <span>
                    {running
                      ? "Deep work in progress…"
                      : `Earn +${focusMinutesSetting} XP on completion`}
                  </span>
                </div>
              </div>

              <div className="timer-buttons">
                <button className="primary btn-with-icon" onClick={() => setRunning((v) => !v)}>
                  <Icon name={running ? "pause" : "play"} size={16} />
                  <span>{running ? "Pause" : "Start session"}</span>
                </button>
                <button className="secondary btn-with-icon" onClick={() => setTimerMode(mode)}>
                  <Icon name="reset" size={16} />
                  <span>Reset</span>
                </button>
              </div>

              <div className="timer-settings-card">
                <label>
                  Focus duration (min)
                  <input
                    type="number"
                    min="1"
                    max="120"
                    value={focusMinutesSetting}
                    onChange={(e) => {
                      const val = Math.max(1, Number(e.target.value) || 1);
                      setFocusMinutesSetting(val);
                      if (mode === "focus" && !running) setRemaining(val * 60);
                    }}
                  />
                </label>
                <label>
                  Break duration (min)
                  <input
                    type="number"
                    min="1"
                    max="60"
                    value={breakMinutesSetting}
                    onChange={(e) => {
                      const val = Math.max(1, Number(e.target.value) || 1);
                      setBreakMinutesSetting(val);
                      if (mode === "break" && !running) setRemaining(val * 60);
                    }}
                  />
                </label>
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">SESSION LOG</p>
                  <h2>Recent focus history</h2>
                </div>
                <span className="badge">{sessions.length} total</span>
              </div>

              {!sessions.length ? (
                <div className="empty">
                  <div className="empty-icon">
                    <Icon name="focus" size={22} />
                  </div>
                  <b>No sessions recorded yet</b>
                  <p>Complete a focus block to save it and earn XP automatically.</p>
                </div>
              ) : (
                <div className="session-list">
                  {sessions.slice(0, 8).map((s) => (
                    <div className="session-card" key={s.id}>
                      <span className="session-badge">
                        <Icon name="check" size={14} />
                      </span>
                      <div className="session-info">
                        <b>{s.duration_minutes}-minute focus block</b>
                        <small>
                          {s.completed_at
                            ? new Date(s.completed_at.endsWith("Z") ? s.completed_at : s.completed_at + "Z").toLocaleString()
                            : "Completed session"}
                        </small>
                      </div>
                      <span className="ach-xp-tag">+{s.duration_minutes} XP</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {activeSection === "habits" && (
          <div className="page-content">
            <section className="panel section-panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">CONSISTENCY OVER INTENSITY</p>
                  <h2>Daily habits</h2>
                  <p className="muted">Track the small routines that compound over time.</p>
                </div>
                <span className="badge">
                  {todayHabits}/{habits.length} completed today
                </span>
              </div>

              <div className="habit-summary-card">
                <div className="habit-summary-top">
                  <div>
                    <b>Today's consistency</b>
                    <p className="muted">
                      {todayHabits} of {habits.length} daily habits checked off
                    </p>
                  </div>
                  <strong className="habit-percent">{habitConsistency}%</strong>
                </div>
                <div className="progress-track">
                  <span style={{ width: `${habitConsistency}%` }} />
                </div>
              </div>

              <form className="habit-form" onSubmit={addHabit}>
                <input
                  value={habitName}
                  onChange={(e) => setHabitName(e.target.value)}
                  placeholder="e.g. Review lecture notes for 20 minutes"
                  maxLength="80"
                  required
                />
                <button className="primary btn-with-icon" type="submit">
                  <Icon name="plus" size={16} />
                  <span>Add habit</span>
                </button>
              </form>

              <div className="habit-list">
                {habits.map((h) => {
                  const checked = (h.completedDates || []).includes(todayKey);
                  const streak = (h.completedDates || []).length;
                  return (
                    <article className={`habit-item ${checked ? "is-checked" : ""}`} key={h.id}>
                      <button
                        className={`check ${checked ? "checked" : ""}`}
                        onClick={() => toggleHabit(h)}
                        aria-label="Toggle habit"
                      >
                        {checked && <Icon name="check" size={13} />}
                      </button>
                      <div className="habit-copy">
                        <b>{h.name}</b>
                        <small>{checked ? "Completed today" : "Pending for today"}</small>
                      </div>
                      <span className="streak-pill">
                        <Icon name="flame" size={14} />
                        <span>
                          {streak} {streak === 1 ? "day" : "days"}
                        </span>
                      </span>
                      <button
                        className="icon-action danger"
                        onClick={() => removeHabit(h.id)}
                        aria-label="Delete habit"
                      >
                        <Icon name="trash" size={14} />
                      </button>
                    </article>
                  );
                })}

                {!habits.length && (
                  <div className="empty">
                    <div className="empty-icon">
                      <Icon name="habits" size={22} />
                    </div>
                    <b>Start with one small habit</b>
                    <p>Add a daily routine you want to build and track your streak.</p>
                  </div>
                )}
              </div>
            </section>
          </div>
        )}

        {activeSection === "analytics" && (
          <div className="page-content analytics-page">
            <section className="stats analytics-stats">
              <Stat label="Tasks created" value={tasks.length} detail="Total workspace tasks" icon="tasks" tone="purple" />
              <Stat label="Tasks completed" value={done} detail={`${completionRate}% completion rate`} icon="check" tone="green" />
              <Stat label="Focus sessions" value={sessions.length} detail="Completed blocks" icon="focus" tone="orange" />
              <Stat label="Total focus time" value={`${Math.floor(focusMinutes / 60)}h ${focusMinutes % 60}m`} detail="Cumulative deep work" icon="trend" tone="blue" />
            </section>

            <section className="analytics-grid">
              <div className="panel completion-panel">
                <div className="panel-head">
                  <div>
                    <p className="eyebrow">TASK PERFORMANCE</p>
                    <h2>Completion overview</h2>
                    <p className="muted">Ratio of finished vs. remaining tasks.</p>
                  </div>
                  <span className="badge">All time</span>
                </div>

                <div className="completion-content">
                  <div className="completion-ring" style={{ "--completion": `${completionRate}%` }}>
                    <div className="completion-ring-inner">
                      <strong>{completionRate}%</strong>
                      <small>completed</small>
                    </div>
                  </div>

                  <div className="completion-legend">
                    <div className="legend-card">
                      <span><i className="legend-dot completed-dot" />Completed</span>
                      <b>{done}</b>
                    </div>
                    <div className="legend-card">
                      <span><i className="legend-dot pending-dot" />Pending</span>
                      <b>{pendingTasks.length}</b>
                    </div>
                    <div className="legend-card">
                      <span><i className="legend-dot total-dot" />Total tasks</span>
                      <b>{tasks.length}</b>
                    </div>
                  </div>
                </div>
              </div>

              <div className="panel history-panel">
                <div className="panel-head">
                  <div>
                    <p className="eyebrow">FOCUS ACTIVITY</p>
                    <h2>Session history</h2>
                    <p className="muted">Your most recent completed sessions.</p>
                  </div>
                  <span className="badge">{sessions.length} total</span>
                </div>

                {sessions.slice(0, 6).map((s) => (
                  <div className="analytics-session" key={s.id}>
                    <span className="session-symbol">
                      <Icon name="focus" size={16} />
                    </span>
                    <div>
                      <b>{s.duration_minutes} minute focus</b>
                      <small>
                        {s.completed_at
                          ? new Date(s.completed_at.endsWith("Z") ? s.completed_at : s.completed_at + "Z").toLocaleString()
                          : "Saved session"}
                      </small>
                    </div>
                    <span className="session-complete">
                      <Icon name="check" size={12} />
                    </span>
                  </div>
                ))}

                {!sessions.length && (
                  <div className="empty">
                    <div className="empty-icon">
                      <Icon name="focus" size={22} />
                    </div>
                    <b>No focus sessions yet</b>
                    <p>Complete a focus session and it will appear here.</p>
                  </div>
                )}
              </div>
            </section>

            <section className="panel priority-panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">WORKLOAD BREAKDOWN</p>
                  <h2>Tasks by priority</h2>
                  <p className="muted">Distribution of your tasks across urgency levels.</p>
                </div>
              </div>

              <div className="priority-chart">
                {["High", "Medium", "Low"].map((level) => {
                  const count = tasks.filter((t) => t.priority === level).length;
                  const percent = tasks.length ? Math.round((count / tasks.length) * 100) : 0;
                  return (
                    <div className={`priority-card ${level.toLowerCase()}`} key={level}>
                      <div className="priority-chart-label">
                        <span>{level} priority</span>
                        <b>{count}</b>
                      </div>
                      <div className="priority-chart-track">
                        <span style={{ width: `${percent}%` }} />
                      </div>
                      <small>{percent}% of total workload</small>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>
        )}

        {activeSection === "assistant" && (
          <div className="page-content ai-page-content">
            <AIAssistantChat
              user={user}
              tasks={tasks}
              sessions={sessions}
              habits={habits}
              progression={progression}
              onStartFocusTask={(card) => {
                const mins = Number(card.estimated_minutes) || 25;
                setFocusMinutesSetting(mins);
                setRemaining(mins * 60);
                setMode("focus");
                setRunning(true);
                setActiveSection("focus");
                addToast({
                  type: "xp",
                  title: "Focus Block Started!",
                  message: `Timer set to ${mins}m for: ${card.title.slice(0, 36)}`,
                  icon: "focus",
                });
              }}
              onToggleTask={toggle}
              onAddTaskDirect={async (card) => {
                try {
                  const data = await api("/tasks", {
                    method: "POST",
                    body: JSON.stringify({
                      title: card.title,
                      category: card.category || "Study",
                      priority: card.priority || "Medium",
                      estimated_minutes: Number(card.estimated_minutes) || 25,
                      due_date: card.due_date || "",
                    }),
                  });
                  setTasks((prev) => [data.task, ...prev]);
                  addToast({
                    type: "xp",
                    title: "Task Added!",
                    message: `Added “${card.title.slice(0, 36)}” to your workspace.`,
                    icon: "check",
                  });
                  return true;
                } catch (err) {
                  setError(err.message);
                  return false;
                }
              }}
              addToast={addToast}
            />
          </div>
        )}

        {activeSection !== "assistant" && (
          <footer>
            <span>FocusFlow · Smart Productivity Management System</span>
            <span>Built for structured study habits & deep work mastery.</span>
          </footer>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value, detail, icon, tone }) {
  return (
    <article className="stat">
      <div className="stat-top">
        <p>{label}</p>
        <div className={`stat-icon ${tone}`}>
          <Icon name={icon} size={18} />
        </div>
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

/* ==================== TOAST NOTIFICATION COMPONENT ==================== */
function ToastNotification({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return (
    <div className="ff-toast-container" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`ff-toast ff-toast-${toast.type}`}>
          <div className="ff-toast-icon">
            <Icon name={toast.icon || "award"} size={20} />
          </div>
          <div className="ff-toast-body">
            <div className="ff-toast-header">
              <b>{toast.title}</b>
              {toast.xp && <span className="ff-toast-xp-pill">+{toast.xp} XP</span>}
            </div>
            <p>{toast.message}</p>
          </div>
          <button
            className="ff-toast-close"
            onClick={() => onDismiss(toast.id)}
            aria-label="Dismiss notification"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

/* ==================== DASHBOARD PROGRESSION WIDGET ==================== */
function DashboardProgressionWidget({ progression, onOpenProgression }) {
  const fallback = {
    current_level: 1,
    level_title: "Beginner",
    rank_tier: "Bronze",
    rank_badge: "bronze",
    current_level_xp: 0,
    next_level_xp: 100,
    total_xp: 0,
    progress_percent: 0,
    weekly_xp: 0,
    next_achievement: {
      name: "First Focus",
      icon: "target",
      xp_reward: 25,
      description: "Complete your first focus session.",
      current_progress: 0,
      target: 1,
    },
  };

  const activeProgression = progression || fallback;
  const {
    current_level = 1,
    level_title = "Beginner",
    rank_tier = "Bronze",
    rank_badge = "bronze",
    current_level_xp = 0,
    next_level_xp = 100,
    total_xp = 0,
    progress_percent = 0,
    weekly_xp = 0,
    next_achievement,
  } = activeProgression;

  const safePercent = Math.min(100, Math.max(0, Number(progress_percent) || 0));
  const fillWidth = current_level_xp > 0 ? Math.max(3, safePercent) : 0;
  const badge = (rank_badge || "bronze").toLowerCase();

  return (
    <section className="progression-widget-card">
      <div className="progression-widget-top">
        <div className="progression-badge-group">
          <div className={`rank-crest rank-${badge}`}>
            <Icon name="award" size={22} />
          </div>
          <div>
            <div className="progression-level-line">
              <span className="level-chip">Level {current_level}</span>
              <span className={`rank-chip rank-${badge}`}>{rank_tier} Tier</span>
            </div>
            <h3 className="progression-title">{level_title}</h3>
          </div>
        </div>

        <div className="progression-widget-stats">
          <div className="stat-pill weekly-xp-pill">
            <span className="stat-pill-icon">
              <Icon name="zap" size={13} />
            </span>
            <span>+{weekly_xp} XP this week</span>
          </div>
          <button className="text-link btn-with-icon" onClick={onOpenProgression}>
            <span>View Profile & Badges</span>
            <Icon name="arrowRight" size={13} />
          </button>
        </div>
      </div>

      <div className="progression-bar-section">
        <div className="progression-bar-labels">
          <span className="progression-bar-current">
            <b>{current_level_xp}</b> / {next_level_xp} XP to Level {current_level + 1} ({Math.round(safePercent)}%)
          </span>
          <span className="progression-bar-total">{total_xp} Total XP</span>
        </div>
        <div className="xp-progress-track">
          <div
            className={`xp-progress-fill rank-fill-${badge}`}
            style={{ width: `${fillWidth}%` }}
          />
        </div>
      </div>

      {next_achievement && (
        <div className="next-achievement-strip" onClick={onOpenProgression}>
          <div className="next-ach-icon">
            <Icon name={next_achievement.icon || "target"} size={16} />
          </div>
          <div className="next-ach-copy">
            <div className="next-ach-title">
              <small>NEXT BADGE</small>
              <b>{next_achievement.name}</b>
              <span className="ach-xp-tag">+{next_achievement.xp_reward} XP</span>
            </div>
            <p>{next_achievement.description}</p>
          </div>
          <div className="next-ach-progress-wrap">
            <span>
              {next_achievement.current_progress || 0} / {next_achievement.target || 1}
            </span>
            <div className="mini-progress-track">
              <div
                className="mini-progress-fill"
                style={{
                  width: `${Math.min(
                    100,
                    Math.round(
                      ((next_achievement.current_progress || 0) / (next_achievement.target || 1)) * 100
                    )
                  )}%`,
                }}
              />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

/* ==================== DEDICATED PROGRESSION & BADGES VIEW ==================== */
function ProgressionSection({ user, progression, onOpenProfileModal }) {
  const [tab, setTab] = useState("achievements");
  const [categoryFilter, setCategoryFilter] = useState("All");

  const fallback = {
    total_xp: 0,
    current_level: 1,
    level_title: "Beginner",
    rank_tier: "Bronze",
    rank_badge: "bronze",
    rank_description: "Foundation of Focus",
    current_level_xp: 0,
    next_level_xp: 100,
    progress_percent: 0,
    total_focus_hours: 0,
    total_sessions: 0,
    current_streak: 0,
    unlocked_achievements_count: 0,
    total_achievements_count: 12,
    achievements: [],
    recent_activity: [],
  };

  const activeProgression = progression || fallback;
  const {
    total_xp = 0,
    current_level = 1,
    level_title = "Beginner",
    rank_tier = "Bronze",
    rank_badge = "bronze",
    rank_description = "Foundation of Focus",
    current_level_xp = 0,
    next_level_xp = 100,
    progress_percent = 0,
    total_focus_hours = 0,
    total_sessions = 0,
    current_streak = 0,
    unlocked_achievements_count = 0,
    total_achievements_count = 12,
    achievements = [],
    recent_activity = [],
  } = activeProgression;

  const safePercent = Math.min(100, Math.max(0, Number(progress_percent) || 0));
  const fillWidth = current_level_xp > 0 ? Math.max(3, safePercent) : 0;
  const badge = (rank_badge || "bronze").toLowerCase();

  const filteredAchievements = achievements.filter((a) => {
    if (categoryFilter === "All") return true;
    if (categoryFilter === "Unlocked") return a.unlocked;
    if (categoryFilter === "Locked") return !a.unlocked;
    return a.category === categoryFilter;
  });

  return (
    <div style={{ display: "grid", gap: 24 }}>
      {/* Premium Hero Progression Card */}
      <section className="progression-hero-card">
        <div className="progression-hero-main">
          <div className="progression-avatar-wrap">
            <div className="progression-avatar">{user.name.trim().charAt(0).toUpperCase()}</div>
            <div className={`progression-avatar-rank rank-crest rank-${badge}`}>
              <Icon name="award" size={16} />
            </div>
          </div>

          <div className="progression-user-meta">
            <div className="progression-user-header">
              <h2 className="progression-user-name">{user.name}</h2>
              <span className={`rank-chip rank-${badge}`}>{rank_tier} Tier</span>
              <span className="level-chip">Level {current_level}</span>
            </div>
            <p className="progression-user-email">{user.email} · {rank_description}</p>

            <div className="progression-title-row">
              <h3>{level_title}</h3>
            </div>

            <div className="progression-hero-bar">
              <div className="progression-hero-bar-meta">
                <span>
                  <b>{current_level_xp}</b> / {next_level_xp} XP to Level {current_level + 1}
                </span>
                <span>
                  <b>{Math.round(safePercent)}%</b> ({total_xp} Total XP)
                </span>
              </div>
              <div className="progression-hero-bar-track">
                <div
                  className={`progression-hero-bar-fill xp-progress-fill rank-fill-${badge}`}
                  style={{ width: `${fillWidth}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Core Matrix Stats */}
        <div className="progression-matrix">
          <div className="progression-matrix-card">
            <div className="progression-matrix-icon blue">
              <Icon name="trend" size={20} />
            </div>
            <div>
              <strong>{total_focus_hours}h</strong>
              <span>Focus Hours Completed</span>
            </div>
          </div>

          <div className="progression-matrix-card">
            <div className="progression-matrix-icon orange">
              <Icon name="focus" size={20} />
            </div>
            <div>
              <strong>{total_sessions}</strong>
              <span>Completed Sessions</span>
            </div>
          </div>

          <div className="progression-matrix-card">
            <div className="progression-matrix-icon red">
              <Icon name="flame" size={20} />
            </div>
            <div>
              <strong>{current_streak} {current_streak === 1 ? "day" : "days"}</strong>
              <span>Productivity Streak</span>
            </div>
          </div>

          <div className="progression-matrix-card">
            <div className="progression-matrix-icon purple">
              <Icon name="trophy" size={20} />
            </div>
            <div>
              <strong>{unlocked_achievements_count} / {total_achievements_count}</strong>
              <span>Badges Unlocked</span>
            </div>
          </div>
        </div>
      </section>

      {/* Navigation Sub-Tabs */}
      <div className="panel">
        <div className="achievements-tabs-row">
          <div className="filter-pill-group">
            <button
              className={`filter-pill ${tab === "achievements" ? "active" : ""}`}
              onClick={() => setTab("achievements")}
            >
              Achievements & Badges ({unlocked_achievements_count}/{total_achievements_count})
            </button>
            <button
              className={`filter-pill ${tab === "ranks" ? "active" : ""}`}
              onClick={() => setTab("ranks")}
            >
              Rank Tiers & Prestige
            </button>
            <button
              className={`filter-pill ${tab === "activity" ? "active" : ""}`}
              onClick={() => setTab("activity")}
            >
              Recent XP Ledger
            </button>
          </div>

          {tab === "achievements" && (
            <div className="filter-pill-group">
              {["All", "Unlocked", "Locked", "Focus", "Tasks", "Consistency", "Discipline"].map((cat) => (
                <button
                  key={cat}
                  className={`filter-pill ${categoryFilter === cat ? "active" : ""}`}
                  onClick={() => setCategoryFilter(cat)}
                  style={{ fontSize: 11, padding: "4px 10px" }}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Tab 1: Achievements Grid */}
        {tab === "achievements" && (
          <div className="achievements-grid">
            {filteredAchievements.map((ach) => (
              <article
                key={ach.id}
                className={`achievement-card ${ach.unlocked ? "unlocked" : "locked"}`}
              >
                <div className="ach-card-top">
                  <div className="ach-icon-box">
                    <Icon name={ach.unlocked ? ach.icon || "award" : "lock"} size={22} />
                  </div>
                  <div className="ach-badges-row">
                    <span className="ach-category-tag">{ach.category}</span>
                    <span className="ach-reward-tag">+{ach.xp_reward} XP</span>
                  </div>
                </div>

                <div className="ach-card-info">
                  <b>{ach.name}</b>
                  <p>{ach.description}</p>
                </div>

                <div className="ach-requirement">
                  <small>Requirement: {ach.requirement}</small>
                </div>

                {!ach.unlocked && ach.target > 1 && (
                  <div style={{ marginTop: 2 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>
                      <span>Progress</span>
                      <span>{ach.current_progress} / {ach.target}</span>
                    </div>
                    <div className="mini-progress-track" style={{ width: "100%" }}>
                      <div
                        className="mini-progress-fill"
                        style={{
                          width: `${Math.min(100, Math.round((ach.current_progress / ach.target) * 100))}%`,
                        }}
                      />
                    </div>
                  </div>
                )}

                <div className="ach-card-footer">
                  {ach.unlocked ? (
                    <span className="ach-unlocked-status">
                      <Icon name="check" size={13} />
                      <span>Unlocked {formatDate(ach.unlocked_at)}</span>
                    </span>
                  ) : (
                    <span className="ach-locked-status">
                      <Icon name="lock" size={12} />
                      <span>Locked</span>
                    </span>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}

        {/* Tab 2: Rank Tiers Roadmap */}
        {tab === "ranks" && (
          <div>
            <p className="muted" style={{ marginBottom: 16 }}>
              Climb through the ranks by earning XP through genuine focus sessions, completed tasks,
              and daily consistency. Each tier unlocks greater prestige and distinction.
            </p>
            <div className="rank-roadmap-grid">
              {[
                { name: "Bronze", badge: "bronze", xp: "0 - 499 XP", desc: "Foundation of Focus" },
                { name: "Silver", badge: "silver", xp: "500 - 1,499 XP", desc: "Consistent Striver" },
                { name: "Gold", badge: "gold", xp: "1,500 - 3,499 XP", desc: "Deep Worker" },
                { name: "Platinum", badge: "platinum", xp: "3,500 - 6,999 XP", desc: "Master of Flow" },
                { name: "Diamond", badge: "diamond", xp: "7,000 - 11,999 XP", desc: "Relentless Discipline" },
                { name: "Master", badge: "master", xp: "12,000+ XP", desc: "Zenith of Productivity" },
              ].map((tier) => {
                const isCurrent = rank_tier.toLowerCase() === tier.name.toLowerCase();
                return (
                  <div
                    key={tier.name}
                    className={`rank-tier-card ${isCurrent ? "is-current" : ""}`}
                  >
                    {isCurrent && <span className="current-rank-marker">Current Rank</span>}
                    <div className={`rank-crest rank-${tier.badge}`} style={{ width: 50, height: 50 }}>
                      <Icon name="award" size={24} />
                    </div>
                    <b>{tier.name}</b>
                    <span className="rank-tier-xp-badge">{tier.xp}</span>
                    <small>{tier.desc}</small>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Tab 3: Recent Activity Ledger */}
        {tab === "activity" && (
          <div>
            <p className="muted" style={{ marginBottom: 16 }}>
              Verifiable log of XP earned from genuine focus sessions, tasks, and consistency streaks.
            </p>
            {!recent_activity.length ? (
              <div className="empty">
                <div className="empty-icon"><Icon name="trend" size={22} /></div>
                <b>No recent XP activities recorded yet</b>
                <p>Complete a focus block or task to earn your first XP points.</p>
              </div>
            ) : (
              <div className="activity-ledger-list">
                {recent_activity.map((item) => (
                  <div className="activity-ledger-item" key={item.id}>
                    <div className="activity-ledger-main">
                      <div className="activity-ledger-icon">
                        <Icon
                          name={
                            item.activity_type === "session"
                              ? "focus"
                              : item.activity_type === "task"
                                ? "check"
                                : item.activity_type === "daily_streak"
                                  ? "flame"
                                  : item.activity_type === "achievement"
                                    ? "award"
                                    : "zap"
                          }
                          size={16}
                        />
                      </div>
                      <div>
                        <b>{item.description}</b>
                        <small>{formatDate(item.created_at)}</small>
                      </div>
                    </div>
                    <span className="activity-ledger-xp">+{item.amount} XP</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ==================== PROFILE MODAL DIALOG ==================== */
function ProfileModal({ user, progression, onClose, onLogout }) {
  return (
    <div className="profile-modal-backdrop" onClick={onClose}>
      <div className="profile-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="profile-modal-top">
          <h2>User Profile & Progression</h2>
          <button className="profile-modal-close" onClick={onClose} aria-label="Close modal">
            ×
          </button>
        </div>

        <ProgressionSection
          user={user}
          progression={progression}
          onOpenProfileModal={() => { }}
        />

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, paddingTop: 16, borderTop: "1px solid var(--border-subtle)" }}>
          <button className="secondary sm" onClick={onClose}>
            Close
          </button>
          <button className="icon-action danger" onClick={onLogout} title="Log out of account" style={{ width: "auto", padding: "6px 14px", display: "inline-flex", gap: 6 }}>
            <Icon name="logout" size={14} />
            <span>Log out</span>
          </button>
        </div>
      </div>
    </div>
  );
}


/* ==================== GEMINI / CHATGPT STYLE AI ASSISTANT ==================== */
function AIAssistantChat({
  user,
  tasks,
  sessions,
  habits,
  progression,
  onStartFocusTask,
  onToggleTask,
  onAddTaskDirect,
  addToast,
}) {
  const [messages, setMessages] = useState(() => {
    try {
      return JSON.parse(
        localStorage.getItem(`ff-ai-messages-${user?.id || "guest"}`) || "[]"
      );
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [aiConfig, setAiConfig] = useState({
    has_key: false,
    masked_key: "",
    models: [],
    recommended_model: "gemini-3.5-flash-lite",
  });
  const [selectedModel, setSelectedModel] = useState(() => {
    const saved = localStorage.getItem("ff-ai-model");
    if (
      !saved ||
      saved.includes("2.5-flash") ||
      saved.includes("1.5-flash") ||
      saved.includes("2.0-flash")
    ) {
      return "gemini-3.5-flash-lite";
    }
    return saved;
  });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [addedCardTitles, setAddedCardTitles] = useState({});
  const messagesEndRef = React.useRef(null);

  // Sync messages to localStorage
  useEffect(() => {
    if (user) {
      localStorage.setItem(
        `ff-ai-messages-${user.id || "guest"}`,
        JSON.stringify(messages)
      );
    }
  }, [messages, user]);

  // Load AI configuration
  const loadConfig = useCallback(async () => {
    try {
      const data = await api("/ai/config");
      setAiConfig(data);
      const saved = localStorage.getItem("ff-ai-model");
      const isDeprecated =
        !saved ||
        saved.includes("2.5-flash") ||
        saved.includes("1.5-flash") ||
        saved.includes("2.0-flash");
      if ((isDeprecated || !saved) && data.recommended_model) {
        setSelectedModel(data.recommended_model);
        localStorage.setItem("ff-ai-model", data.recommended_model);
      }
    } catch (e) {
      console.warn("Could not load AI config", e);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(promptText = input) {
    const text = (promptText || "").trim();
    if (!text || loading) return;

    const userMsg = { role: "user", content: text };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput("");
    setLoading(true);

    try {
      const data = await api("/ai/chat", {
        method: "POST",
        body: JSON.stringify({
          messages: updatedMessages,
          model: selectedModel,
        }),
      });

      const assistantMsg = {
        role: "model",
        content: data.reply,
        cards: data.cards || [],
        model_used: data.model_used,
      };

      setMessages((prev) => [...prev, assistantMsg]);

      if (data.needs_key) {
        setSettingsOpen(true);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "model",
          content: `⚠️ **Error**: ${err.message}. Please check your connection or Gemini API key.`,
          cards: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function clearChat() {
    if (window.confirm("Clear this conversation history?")) {
      setMessages([]);
      localStorage.removeItem(`ff-ai-messages-${user?.id || "guest"}`);
    }
  }

  const starterCards = [
    {
      id: "prioritize",
      icon: "target",
      tone: "purple",
      title: "What should I prioritize right now?",
      desc: "Analyze my deadlines and high-priority tasks to suggest the best start.",
      prompt: "What task should I focus on right now based on my deadlines, priorities, and current focus history?",
    },
    {
      id: "pomodoro",
      icon: "focus",
      tone: "orange",
      title: "Plan a 2-hour Pomodoro study block",
      desc: "Structure 25-minute deep focus sessions and breaks around my active tasks.",
      prompt: "Create a 2-hour Pomodoro study plan for me. Break down my pending tasks into 25-minute focus blocks and 5-minute breaks.",
    },
    {
      id: "breakdown",
      icon: "zap",
      tone: "green",
      title: "Break down my hardest task",
      desc: "Divide my high-priority assignment into smaller, actionable sub-steps.",
      prompt: "Take my highest-priority task and break it down into 3 or 4 actionable sub-tasks with estimated minutes for each.",
    },
    {
      id: "streak",
      icon: "trend",
      tone: "blue",
      title: "Analyze my productivity & habits",
      desc: "Evaluate my consistency, XP progress, and how to reach the next milestone.",
      prompt: "Analyze my recent productivity, current streak, and habits. How can I stay consistent and reach my next level faster?",
    },
  ];

  const pendingCount = tasks.filter((t) => !t.completed).length;

  return (
    <div className="ai-chat-shell">
      {/* Settings Modal */}
      {settingsOpen && (
        <AISettingsModal
          aiConfig={aiConfig}
          selectedModel={selectedModel}
          onSelectModel={(m) => {
            setSelectedModel(m);
            localStorage.setItem("ff-ai-model", m);
          }}
          onSaveKey={async (key) => {
            const res = await api("/ai/config", {
              method: "POST",
              body: JSON.stringify({ api_key: key }),
            });
            setAiConfig(res);
            if (res.recommended_model) {
              setSelectedModel(res.recommended_model);
              localStorage.setItem("ff-ai-model", res.recommended_model);
            }
            addToast({
              type: "xp",
              title: "Gemini API Connected!",
              message: `Active model set to ${res.recommended_model} (Low Credit usage).`,
              icon: "sparkle",
            });
            setSettingsOpen(false);
          }}
          onClose={() => setSettingsOpen(false)}
        />
      )}

      {/* Header Bar */}
      <div className="ai-chat-header">
        <div className="ai-header-left">
          <div className="ai-avatar-orb">
            <Icon name="sparkle" size={18} />
          </div>
          <div className="ai-header-info">
            <h2>
              <span>FocusFlow AI Assistant</span>
            </h2>
            <p>
              Grounded in {pendingCount} tasks · {progression?.current_streak || 0}-day streak · Level{" "}
              {progression?.current_level || 1} ({progression?.rank_tier || "Bronze"})
            </p>
          </div>
        </div>

        <div className="ai-header-actions">
          <button
            className="ai-model-pill"
            onClick={() => setSettingsOpen(true)}
            title="Click to change model or view credit usage"
          >
            <Icon name="sparkle" size={13} />
            <span>{selectedModel}</span>
          </button>

          <button
            className={`ai-key-btn ${aiConfig.has_key ? "has-key" : "needs-key"}`}
            onClick={() => setSettingsOpen(true)}
          >
            <Icon name="key" size={13} />
            <span>{aiConfig.has_key ? "Gemini Key Connected" : "Connect Gemini Key"}</span>
          </button>

          {messages.length > 0 && (
            <button
              className="icon-action"
              onClick={clearChat}
              title="Clear conversation"
              aria-label="Clear conversation"
            >
              <Icon name="trash" size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Chat Body */}
      <div className="ai-chat-body">
        {messages.length === 0 ? (
          <div className="ai-welcome-box">
            <div className="ai-welcome-orb">
              <Icon name="sparkle" size={28} />
            </div>
            <h2>How can I assist your study flow today?</h2>
            <p>
              I am your personal productivity assistant powered by Google Gemini. I have real-time
              access to your tasks, focus sessions, and habit consistency to give you practical,
              actionable guidance.
            </p>
            <div className="ai-context-chip">
              <Icon name="checkCircle" size={14} />
              <span>
                {pendingCount} active tasks · {sessions.length} focus sessions logged
              </span>
            </div>

            {/* Starter Prompt Cards */}
            <div className="ai-starter-grid">
              {starterCards.map((card) => (
                <div
                  key={card.id}
                  className="ai-starter-card"
                  onClick={() => handleSend(card.prompt)}
                >
                  <div className={`ai-starter-icon ${card.tone}`}>
                    <Icon name={card.icon} size={18} />
                  </div>
                  <div className="ai-starter-copy">
                    <b>{card.title}</b>
                    <span>{card.desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div key={index} className={`ai-message-row ${msg.role === "user" ? "user" : "assistant"}`}>
              <div className="ai-msg-avatar">
                {msg.role === "user" ? (
                  user?.name?.trim().charAt(0).toUpperCase() || "U"
                ) : (
                  <Icon name="sparkle" size={16} />
                )}
              </div>

              <div className="ai-msg-content">
                <div className="ai-bubble">
                  {msg.role === "user" ? msg.content : renderMarkdown(msg.content)}
                </div>
                {msg.role !== "user" && msg.model_used && (
                  <div className="ai-model-attribution">
                    <Icon name="sparkle" size={11} />
                    <span>Answered by {msg.model_used}</span>
                  </div>
                )}

                {/* Task Cards rendered under assistant response */}
                {msg.cards && msg.cards.length > 0 && (
                  <div className="ai-cards-group">
                    {msg.cards.map((card, cIdx) => {
                      const isAdded = addedCardTitles[card.title];
                      return (
                        <div
                          key={cIdx}
                          className={`ai-task-card ${card.type === "new_task_suggestion" ? "new-task" : ""
                            }`}
                        >
                          <div className="ai-task-card-main">
                            <div className="ai-task-card-header">
                              <span className="ach-category-tag">
                                {card.type === "new_task_suggestion" ? "Suggested Task" : card.category}
                              </span>
                              <span
                                className={`priority ${(card.priority || "Medium").toLowerCase()}`}
                                style={{ fontSize: 10, padding: "2px 7px" }}
                              >
                                {card.priority}
                              </span>
                            </div>
                            <b>{card.title}</b>
                            <div className="ai-task-card-meta">
                              <span>⏱️ {card.estimated_minutes} min focus</span>
                              {card.due_date && <span>📅 Due {card.due_date}</span>}
                            </div>
                          </div>

                          <div className="ai-task-card-actions">
                            {card.type === "existing_task" ? (
                              <>
                                <button
                                  className="primary sm btn-with-icon"
                                  onClick={() => onStartFocusTask(card)}
                                  title="Start a focus timer for this task"
                                >
                                  <Icon name="play" size={13} />
                                  <span>Start Focus</span>
                                </button>
                                {!card.completed && (
                                  <button
                                    className="secondary sm btn-with-icon"
                                    onClick={() => onToggleTask(card)}
                                    title="Complete this task (+10 XP)"
                                  >
                                    <Icon name="check" size={13} />
                                    <span>Complete (+10 XP)</span>
                                  </button>
                                )}
                              </>
                            ) : (
                              <button
                                className="primary sm btn-with-icon"
                                disabled={isAdded}
                                onClick={async () => {
                                  const success = await onAddTaskDirect(card);
                                  if (success) {
                                    setAddedCardTitles((prev) => ({ ...prev, [card.title]: true }));
                                  }
                                }}
                              >
                                <Icon name={isAdded ? "check" : "plus"} size={13} />
                                <span>{isAdded ? "Added to Workspace ✓" : "+ Add to Tasks"}</span>
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="ai-message-row assistant">
            <div className="ai-msg-avatar">
              <Icon name="sparkle" size={16} />
            </div>
            <div className="ai-typing-indicator">
              <span className="ai-dot" />
              <span className="ai-dot" />
              <span className="ai-dot" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="ai-input-wrap">
        <form
          className="ai-input-form"
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
        >
          <input
            className="ai-input-field"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask FocusFlow AI about your priorities, study schedule, or breakdown of tasks..."
            disabled={loading}
          />
          <button
            type="submit"
            className="ai-send-btn"
            disabled={!input.trim() || loading}
            aria-label="Send message"
          >
            <Icon name="send" size={16} />
          </button>
        </form>
        <div className="ai-input-foot">
          <span>🔒 Grounded in your private workspace data</span>
          <span>Powered by Google Gemini · Low Credit Usage</span>
        </div>
      </div>
    </div>
  );
}

/* ==================== AI SETTINGS & MODEL SELECTION MODAL ==================== */
function AISettingsModal({ aiConfig, selectedModel, onSelectModel, onSaveKey, onClose }) {
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSaveKey(e) {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setSaving(true);
    setError("");
    try {
      await onSaveKey(apiKey.trim());
    } catch (err) {
      setError(err.message || "Failed to verify Gemini API Key.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="profile-modal-backdrop" onClick={onClose}>
      <div
        className="profile-modal-card ai-settings-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="profile-modal-top">
          <h2>Google Gemini Configuration</h2>
          <button className="profile-modal-close" onClick={onClose} aria-label="Close dialog">
            ×
          </button>
        </div>

        <form onSubmit={handleSaveKey} className="ai-modal-section">
          <label>
            Gemini API Key
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={aiConfig.has_key ? `Connected (${aiConfig.masked_key})` : "Paste your Gemini API key (AIzaSy...)"}
              required={!aiConfig.has_key}
            />
          </label>
          <p className="ai-key-hint">
            Get your free Gemini API key in 30 seconds at{" "}
            <a
              href="https://aistudio.google.com/app/apikey"
              target="_blank"
              rel="noopener noreferrer"
            >
              Google AI Studio
            </a>
            . Your key is stored securely in your private workspace.
          </p>

          {error && <div className="error">{error}</div>}

          <div style={{ display: "flex", gap: 10 }}>
            <button className="primary sm btn-with-icon" type="submit" disabled={saving || !apiKey.trim()}>
              <Icon name="key" size={14} />
              <span>{saving ? "Verifying & Discovering Models…" : "Save & Verify Key"}</span>
            </button>
          </div>
        </form>

        <div className="ai-modal-section" style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 16 }}>
          <b>Available Gemini Models (Lowest Credit Usage Prioritized)</b>
          <p className="muted" style={{ fontSize: 12 }}>
            We automatically select Flash models for minimal credit consumption and instant responses.
          </p>

          <div className="ai-model-list">
            {(aiConfig.models && aiConfig.models.length > 0
              ? aiConfig.models
              : [
                { id: "gemini-3.5-flash-lite", display_name: "Gemini 3.5 Flash Lite", credit_tier: "Ultra Low Credit (Flash-Lite)" },
                { id: "gemini-flash-lite-latest", display_name: "Gemini Flash-Lite Latest", credit_tier: "Ultra Low Credit (Flash-Lite)" },
                { id: "gemini-3.8-flash", display_name: "Gemini 3.8 Flash", credit_tier: "Low Credit (Latest Flash)" },
                { id: "gemini-3.5-flash", display_name: "Gemini 3.5 Flash", credit_tier: "Low Credit" },
                { id: "gemini-2.5-pro", display_name: "Gemini 2.5 Pro", credit_tier: "Higher Credit (Pro)" },
              ]
            ).map((m) => {
              const isSelected = selectedModel === m.id;
              return (
                <div
                  key={m.id}
                  className={`ai-model-option ${isSelected ? "selected" : ""}`}
                  onClick={() => onSelectModel(m.id)}
                >
                  <div className="ai-model-opt-info">
                    <b>{m.display_name || m.id}</b>
                    <small>{m.id}</small>
                  </div>
                  <span className="ai-tier-tag">{m.credit_tier || "Standard"}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button className="secondary sm" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

/* ==================== MARKDOWN RENDERER ==================== */
function renderMarkdown(text) {
  if (!text) return null;
  const lines = text.split("\n");
  const elements = [];
  let listItems = [];

  const flushList = (key) => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${key}`}>
          {listItems.map((item, idx) => (
            <li key={idx} dangerouslySetInnerHTML={{ __html: formatInline(item) }} />
          ))}
        </ul>
      );
      listItems = [];
    }
  };

  const formatInline = (str) => {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  };

  lines.forEach((line, i) => {
    const trimmed = line.trim();
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      listItems.push(trimmed.slice(2));
    } else if (/^\d+\.\s/.test(trimmed)) {
      listItems.push(trimmed.replace(/^\d+\.\s/, ""));
    } else {
      flushList(i);
      if (trimmed.startsWith("### ")) {
        elements.push(<h4 key={i}>{trimmed.slice(4)}</h4>);
      } else if (trimmed.startsWith("## ")) {
        elements.push(<h3 key={i}>{trimmed.slice(3)}</h3>);
      } else if (trimmed) {
        elements.push(
          <p key={i} dangerouslySetInnerHTML={{ __html: formatInline(trimmed) }} />
        );
      }
    }
  });
  flushList("end");
  return elements;
}
