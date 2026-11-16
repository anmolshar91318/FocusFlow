import React, { useCallback, useEffect, useMemo, useState } from "react";

const API = "http://localhost:5000/api";
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
  const [activeSection, setActiveSection] = useState("dashboard");
  const [tasks, setTasks] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("Study");
  const [priority, setPriority] = useState("Medium");
  const [dueDate, setDueDate] = useState("");
  const [estimate, setEstimate] = useState("30");
  const [editingTaskId, setEditingTaskId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");

  const [mode, setMode] = useState("focus");
  const [focusMinutesSetting, setFocusMinutesSetting] = useState(25);
  const [breakMinutesSetting, setBreakMinutesSetting] = useState(5);
  const [remaining, setRemaining] = useState(FOCUS_SECONDS);
  const [running, setRunning] = useState(false);

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

  useEffect(() => {
    if (user) {
      localStorage.setItem(`ff-habits-${user.id || user.email}`, JSON.stringify(habits));
    }
  }, [habits, user]);

  useEffect(() => {
    localStorage.setItem("focusflow-theme", nightMode ? "night" : "day");
  }, [nightMode]);

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
      const [t, s] = await Promise.all([api("/tasks"), api("/sessions")]);
      setTasks(t.tasks);
      setSessions(s.sessions);
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
      } catch {}
    } else {
      setTasks([]);
      setSessions([]);
    }
  }, [user, refresh]);

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
    setRunning(false);
    setProfileOpen(false);
  }

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
            .then(refresh)
            .catch((e) => setError(e.message));
          window.alert("Focus session complete! Take a short break.");
          setMode("break");
          return breakMinutesSetting * 60;
        }
        window.alert("Break complete! Ready for another focus session?");
        setMode("focus");
        return focusMinutesSetting * 60;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [running, mode, refresh, user, focusMinutesSetting, breakMinutesSetting]);

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
    return `Start with “${t.title}”. It is ${t.priority.toLowerCase()} priority${
      t.due_date ? ` and is due ${t.due_date}` : ""
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
          <p className="auth-foot">Your tasks and focus history are kept in your own account.</p>
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
          <p className="eyebrow">SMALL STEPS ADD UP</p>
          <h2>Make room for your best work.</h2>
          <p>
            Plan your tasks, protect your focus time, and celebrate the progress you make every day.
          </p>
          <div className="auth-quote">
            “A little progress each day adds up to big results.”
          </div>
        </aside>
      </div>
    );
  }

  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: "dashboard" },
    { id: "tasks", label: "Task management", icon: "tasks" },
    { id: "focus", label: "Focus timer", icon: "focus" },
    { id: "habits", label: "Habit tracker", icon: "habits" },
    { id: "analytics", label: "Analytics & reports", icon: "analytics" },
    { id: "assistant", label: "AI assistant", icon: "assistant" },
  ];

  const pageMeta = {
    dashboard: ["Dashboard", "Your productivity overview and daily priorities at a glance."],
    tasks: ["Task management", "Plan, prioritize, and keep every commitment organized."],
    focus: ["Focus timer", "Protect your attention with structured work and break sessions."],
    habits: ["Habit tracker", "Build consistency through small, repeatable daily actions."],
    analytics: ["Analytics & reports", "Understand your completion trends and focus patterns."],
    assistant: ["AI productivity assistant", "Practical, transparent suggestions based on your workload."],
  };

  return (
    <div className={`layout ff-layout ${nightMode ? "dark" : ""}`} data-theme={nightMode ? "night" : "day"}>
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

        <div className="side-note">
          <div className="side-note-icon">
            <Icon name="assistant" size={16} />
          </div>
          <b>Small steps add up.</b>
          <p>Make steady progress one focused block at a time.</p>
        </div>

        <div className="side-footer">
          <span>MCA MINOR PROJECT</span>
          <b>Smart Productivity System</b>
        </div>
      </aside>

      <main className="main ff-main">
        <header className="header">
          <div className="header-title">
            <p className="eyebrow">FOCUSFLOW WORKSPACE</p>
            <h1>
              {pageMeta[activeSection][0]}
              <span>.</span>
            </h1>
            <p className="muted">{pageMeta[activeSection][1]}</p>
          </div>

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
              <button className="profile-button" onClick={() => setProfileOpen((v) => !v)}>
                <span className="avatar">{user.name.trim().charAt(0).toUpperCase()}</span>
                <span className="profile-name">{user.name}</span>
                <span className="profile-chevron">⌄</span>
              </button>
              {profileOpen && (
                <div className="profile-menu">
                  <div className="profile-menu-info">
                    <b>{user.name}</b>
                    <small>{user.email}</small>
                  </div>
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
                    <span>Start a focus session</span>
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

        {activeSection === "tasks" && (
          <div className="page-content">
            <section className="panel section-panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">PLAN YOUR WORK</p>
                  <h2>Create a new task</h2>
                  <p className="muted">Capture tasks, assign priorities, and estimate effort.</p>
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
                  <p className="eyebrow">DEEP WORK</p>
                  <h2>Pomodoro timer</h2>
                </div>
                <span className="badge">{mode === "focus" ? "Focus Mode" : "Rest Mode"}</span>
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
                  <span>{running ? "Session in progress…" : "Ready when you are"}</span>
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
                  <p>Complete a focus block to save it automatically to your account.</p>
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
                            ? new Date(s.completed_at + "Z").toLocaleString()
                            : "Completed session"}
                        </small>
                      </div>
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
                          ? new Date(s.completed_at + "Z").toLocaleString()
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
          <div className="page-content">
            <section className="panel assistant-panel">
              <div className="assistant-heading">
                <span className="assistant-orb">
                  <Icon name="assistant" size={24} />
                </span>
                <div>
                  <p className="eyebrow">PRODUCTIVITY COACH</p>
                  <h2>Your next best move</h2>
                  <p className="muted">
                    Rule-based recommendations derived directly from your deadlines and priorities.
                  </p>
                </div>
              </div>

              <div className="recommendation">
                <span className="recommendation-label">RECOMMENDED ACTION</span>
                <p>{suggestionText}</p>
                <button className="primary btn-with-icon" onClick={() => setActiveSection("tasks")}>
                  <span>Review my tasks</span>
                  <Icon name="arrowRight" size={15} />
                </button>
              </div>

              <div className="assistant-cards">
                <article className="strategy-card">
                  <div className="strategy-icon purple">
                    <Icon name="tasks" size={18} />
                  </div>
                  <b>Prioritize urgent work</b>
                  <p>
                    Start with high-priority tasks or anything due today. Break larger deliverables
                    into smaller, achievable steps.
                  </p>
                </article>

                <article className="strategy-card">
                  <div className="strategy-icon orange">
                    <Icon name="focus" size={18} />
                  </div>
                  <b>Protect your focus</b>
                  <p>
                    Commit to a {focusMinutesSetting}-minute deep work block, silence notifications,
                    and take a {breakMinutesSetting}-minute break afterward.
                  </p>
                  <button className="text-link btn-with-icon" onClick={() => setActiveSection("focus")}>
                    <span>Open focus timer</span>
                    <Icon name="arrowRight" size={13} />
                  </button>
                </article>

                <article className="strategy-card">
                  <div className="strategy-icon green">
                    <Icon name="habits" size={18} />
                  </div>
                  <b>Build a repeatable routine</b>
                  <p>
                    Focus on one daily habit you can sustain effortlessly. Consistency beats
                    occasional bursts of intensity.
                  </p>
                  <button className="text-link btn-with-icon" onClick={() => setActiveSection("habits")}>
                    <span>Open habit tracker</span>
                    <Icon name="arrowRight" size={13} />
                  </button>
                </article>
              </div>
            </section>
          </div>
        )}

        <footer>
          <span>FocusFlow · Smart Productivity Management System</span>
          <span>Built for structured study habits.</span>
        </footer>
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
