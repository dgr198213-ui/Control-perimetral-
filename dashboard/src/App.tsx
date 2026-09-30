/*
 * Dirección visual: "Instrumento de Campo".
 * Dashboard editorial oscuro, asimétrico y sobrio; usa grafito, hueso y ámbar
 * para traducir una herramienta local de seguridad en una superficie legible,
 * no en una consola cyberpunk. El layout privilegia jerarquía, trazabilidad y
 * estados honestos: nunca inventa telemetría de producción.
 */
import { FormEvent, useEffect, useMemo, useState } from "react";
import "./styles.css";

type IconName =
  | "activity"
  | "alert"
  | "arrow"
  | "camera"
  | "check"
  | "chevron"
  | "globe"
  | "home"
  | "lock"
  | "logout"
  | "menu"
  | "moon"
  | "settings"
  | "shield"
  | "sun";

type Language = "es" | "en";
type RouteKey = "summary" | "cameras" | "map" | "alerts" | "settings";

type Compliance = {
  signage_confirmed: boolean;
  mandate_confirmed: boolean;
  kill_switch: boolean;
  recording_allowed: boolean;
  updated_at: string;
};

type Camera = { id: string; name: string; enabled: boolean };
type AuditEntry = { action: string; entity: string; created_at: string };

const copy = {
  es: {
    appName: "CONTROL / PERIMETRAL",
    local: "OPERACIÓN LOCAL",
    signIn: "Acceso al panel",
    signInHint: "Tu infraestructura queda en tu red. La sesión solo abre el control local.",
    username: "Usuario",
    password: "Contraseña",
    usernamePlaceholder: "usuario de operación",
    passwordPlaceholder: "mínimo 12 caracteres",
    enter: "Entrar al panel",
    signingIn: "Comprobando sesión…",
    invalid: "No se ha podido abrir la sesión. Comprueba las credenciales.",
    apiUnavailable: "API local no disponible · vista segura de demostración",
    nav: { summary: "Resumen", cameras: "Cámaras", map: "Mapa", alerts: "Alertas", settings: "Configuración" },
    summaryEyebrow: "Puesto de control / 01",
    summaryTitle: "La finca, en una sola lectura.",
    summaryIntro: "Estado operativo del perímetro y sus condiciones de cumplimiento. Sin nube. Sin telemetría inventada.",
    updated: "Última comprobación",
    compliance: "Cumplimiento",
    enabled: "Apto para operar",
    blocked: "Bloqueado hasta confirmar",
    killSwitch: "Corte de seguridad activo",
    cameras: "Cámaras configuradas",
    camerasHint: "Fuentes registradas en control-api",
    events: "Eventos auditados",
    eventsHint: "Trazas locales persistentes",
    recording: "Grabación",
    recordingOn: "Permitida por cumplimiento",
    recordingOff: "Desactivada por defecto",
    access: "Estado de acceso",
    localOnly: "Red local únicamente",
    activity: "Actividad reciente",
    noActivity: "Aún no hay actividad operativa registrada.",
    auditHint: "Las acciones de configuración se conservan en una bitácora inmutable.",
    protected: "Superficie protegida",
    protectedHint: "Los secretos nunca se muestran en el panel ni en la configuración renderizada.",
    configure: "Ir a configuración",
    moduleReserved: "Módulo reservado",
    moduleHint: "La estructura de navegación ya está lista. Esta superficie se habilitará en el siguiente hito, sin datos de relleno.",
    backSummary: "Volver al resumen",
    signOut: "Cerrar sesión",
    language: "Idioma",
    theme: "Tema",
    light: "Claro",
    dark: "Oscuro",
    system: "Sistema",
    secure: "Conexión local · sesión protegida",
    version: "BASE 0.1",
  },
  en: {
    appName: "CONTROL / PERIMETER",
    local: "LOCAL OPERATION",
    signIn: "Panel access",
    signInHint: "Your infrastructure stays on your network. The session only opens local control.",
    username: "Username",
    password: "Password",
    usernamePlaceholder: "operations user",
    passwordPlaceholder: "minimum 12 characters",
    enter: "Enter panel",
    signingIn: "Checking session…",
    invalid: "The session could not be opened. Check your credentials.",
    apiUnavailable: "Local API unavailable · safe demo view",
    nav: { summary: "Summary", cameras: "Cameras", map: "Map", alerts: "Alerts", settings: "Settings" },
    summaryEyebrow: "Control post / 01",
    summaryTitle: "The property, at a glance.",
    summaryIntro: "Perimeter operations and compliance conditions. No cloud. No invented telemetry.",
    updated: "Last check",
    compliance: "Compliance",
    enabled: "Ready to operate",
    blocked: "Blocked until confirmed",
    killSwitch: "Safety cut-off active",
    cameras: "Configured cameras",
    camerasHint: "Sources registered in control-api",
    events: "Audited events",
    eventsHint: "Persistent local traces",
    recording: "Recording",
    recordingOn: "Allowed by compliance",
    recordingOff: "Disabled by default",
    access: "Access status",
    localOnly: "Local network only",
    activity: "Recent activity",
    noActivity: "No operational activity has been recorded yet.",
    auditHint: "Configuration actions are kept in an immutable log.",
    protected: "Protected surface",
    protectedHint: "Secrets never appear in the panel or rendered configuration.",
    configure: "Open settings",
    moduleReserved: "Reserved module",
    moduleHint: "Navigation is ready. This surface will be enabled in the next milestone, without placeholder data.",
    backSummary: "Back to summary",
    signOut: "Sign out",
    language: "Language",
    theme: "Theme",
    light: "Light",
    dark: "Dark",
    system: "System",
    secure: "Local connection · protected session",
    version: "BASE 0.1",
  },
} as const;

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, string> = {
    activity: "M3 12h4l2-8 4 16 2-8h6",
    alert: "M10.3 4.3 2.8 17a1.5 1.5 0 0 0 1.3 2.2h15.8a1.5 1.5 0 0 0 1.3-2.2L13.7 4.3a2 2 0 0 0-3.4 0ZM12 9v4m0 3h.01",
    arrow: "M5 12h14m-6-6 6 6-6 6",
    camera: "M4 7h3l1.5-2h7L17 7h3v11H4V7Zm4 5a4 4 0 1 0 8 0 4 4 0 0 0-8 0Z",
    check: "m5 12 4 4L19 6",
    chevron: "m9 18 6-6-6-6",
    globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-18c2.2 2.4 3.3 5.4 3.3 9S14.2 18.6 12 21m0-18C9.8 5.4 8.7 8.4 8.7 12s1.1 6.6 3.3 9M3 12h18",
    home: "m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V10Zm6 11v-6h6v6",
    lock: "M6 10V8a6 6 0 0 1 12 0v2m-13 0h14v10H5V10Zm7 4v2",
    logout: "M10 17l5-5-5-5m5 5H3m12-7V4a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-1",
    menu: "M4 6h16M4 12h16M4 18h16",
    moon: "M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5 8.5 8.5 0 1 0 20.5 14.5Z",
    settings: "M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Zm8-3.2-1.7-.6a6.8 6.8 0 0 0-.5-1.2l.8-1.6-1.9-1.9-1.6.8a6.8 6.8 0 0 0-1.2-.5L13.3 5h-2.6l-.6 1.7a6.8 6.8 0 0 0-1.2.5l-1.6-.8-1.9 1.9.8 1.6a6.8 6.8 0 0 0-.5 1.2L4 12v2l1.7.6c.1.4.3.8.5 1.2l-.8 1.6 1.9 1.9 1.6-.8c.4.2.8.4 1.2.5l.6 1.7h2.6l.6-1.7a6.8 6.8 0 0 0 1.2-.5l1.6.8 1.9-1.9-.8-1.6c.2-.4.4-.8.5-1.2L20 14v-2Z",
    shield: "M12 3 20 6v5c0 5.1-3.4 8.7-8 10-4.6-1.3-8-4.9-8-10V6l8-3Zm-3 9 2 2 4-4",
    sun: "M12 3v2m0 14v2M5.6 5.6 7 7m10 10 1.4 1.4M3 12h2m14 0h2M5.6 18.4 7 17m10-10 1.4-1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  };
  return <svg aria-hidden="true" className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name]} /></svg>;
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, { credentials: "include", ...options });
  if (!response.ok) throw new Error(`${response.status}`);
  return response.json() as Promise<T>;
}

function Login({ language, onLanguage, onLoggedIn }: { language: Language; onLanguage: () => void; onLoggedIn: () => void }) {
  const t = copy[language];
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await api("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
      sessionStorage.setItem("perimetral-auth", "1"); onLoggedIn();
    } catch { setError(t.invalid); } finally { setBusy(false); }
  };
  return <main className="login-page">
    <div className="login-atmosphere" aria-hidden="true"><span className="horizon" /><span className="coordinate coordinate-a">N 40° 24′ 12″</span><span className="coordinate coordinate-b">W 003° 42′ 19″</span></div>
    <section className="login-panel">
      <div className="brand-lockup"><div className="brand-mark"><Icon name="shield" size={25} /></div><div><strong>{t.appName}</strong><span>{t.local}</span></div></div>
      <div className="login-copy"><p className="eyebrow">{t.version}</p><h1>{t.signIn}</h1><p>{t.signInHint}</p></div>
      <form onSubmit={submit} className="login-form">
        <label>{t.username}<input value={username} onChange={(e) => setUsername(e.target.value)} placeholder={t.usernamePlaceholder} autoComplete="username" required /></label>
        <label>{t.password}<input value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t.passwordPlaceholder} type="password" autoComplete="current-password" minLength={12} required /></label>
        {error && <div className="form-error" role="alert"><Icon name="alert" size={16} />{error}</div>}
        <button className="primary-button" disabled={busy}>{busy ? t.signingIn : <>{t.enter}<Icon name="arrow" size={17} /></>}</button>
      </form>
      <footer className="login-footer"><span><Icon name="lock" size={14} />{t.secure}</span><button className="language-button" onClick={onLanguage}>{language === "es" ? "EN" : "ES"}<Icon name="globe" size={14} /></button></footer>
    </section>
  </main>;
}

function Nav({ route, setRoute, language, compact }: { route: RouteKey; setRoute: (route: RouteKey) => void; language: Language; compact: boolean }) {
  const t = copy[language];
  const items: { key: RouteKey; icon: IconName; label: string }[] = [
    { key: "summary", icon: "home", label: t.nav.summary }, { key: "cameras", icon: "camera", label: t.nav.cameras }, { key: "map", icon: "globe", label: t.nav.map }, { key: "alerts", icon: "alert", label: t.nav.alerts }, { key: "settings", icon: "settings", label: t.nav.settings },
  ];
  return <nav className={`sidebar ${compact ? "compact" : ""}`} aria-label="Navegación principal">
    <div className="sidebar-brand"><div className="brand-mark small"><Icon name="shield" size={19} /></div>{!compact && <div><strong>{t.appName}</strong><span>{t.local}</span></div>}</div>
    <div className="nav-group"><p className="nav-label">{language === "es" ? "Operación" : "Operations"}</p>{items.map((item) => <button key={item.key} className={`nav-item ${route === item.key ? "active" : ""}`} onClick={() => setRoute(item.key)} aria-current={route === item.key ? "page" : undefined}><Icon name={item.icon} size={18} /><span>{item.label}</span>{route === item.key && <i />}</button>)}</div>
    <div className="sidebar-bottom"><div className="system-note"><span className="signal-dot" /><span>{language === "es" ? "Sistema local" : "Local system"}</span></div><span className="version-tag">{t.version}</span></div>
  </nav>;
}

function Summary({ language, compliance, cameras, audit, demo, setRoute }: { language: Language; compliance: Compliance; cameras: Camera[]; audit: AuditEntry[]; demo: boolean; setRoute: (route: RouteKey) => void }) {
  const t = copy[language];
  const statusLabel = compliance.kill_switch ? t.killSwitch : compliance.recording_allowed ? t.enabled : t.blocked;
  const statusClass = compliance.kill_switch ? "danger" : compliance.recording_allowed ? "good" : "warn";
  return <div className="page-content">
    {demo && <div className="demo-banner"><span className="signal-dot" />{t.apiUnavailable}</div>}
    <div className="page-heading"><div><p className="eyebrow">{t.summaryEyebrow}</p><h1>{t.summaryTitle}</h1><p className="lede">{t.summaryIntro}</p></div><div className="heading-meta"><span className="live-chip"><span className="signal-dot" />{t.local}</span><span className="updated-label">{t.updated} · {new Date().toLocaleTimeString(language === "es" ? "es-ES" : "en-US", { hour: "2-digit", minute: "2-digit" })}</span></div></div>
    <section className="status-hero"><div className="status-orbit" aria-hidden="true"><div className="orbit-line orbit-one" /><div className="orbit-line orbit-two" /><div className="orbit-core"><Icon name={statusClass === "good" ? "check" : "shield"} size={30} /></div></div><div className="status-copy"><p className="eyebrow">{t.compliance}</p><h2>{statusLabel}</h2><p>{compliance.recording_allowed ? t.recordingOn : t.recordingOff}</p><button className="text-button" onClick={() => setRoute("settings")}>{t.configure}<Icon name="arrow" size={16} /></button></div><div className={`status-stamp ${statusClass}`}><span>{compliance.kill_switch ? "STOP" : compliance.recording_allowed ? "OK" : "HOLD"}</span><small>{compliance.kill_switch ? "KILL SWITCH" : "LOCAL GATE"}</small></div></section>
    <section className="stat-grid"><article className="stat-card"><div className="stat-top"><span>{t.cameras}</span><Icon name="camera" size={17} /></div><strong>{cameras.length}</strong><p>{t.camerasHint}</p></article><article className="stat-card"><div className="stat-top"><span>{t.events}</span><Icon name="activity" size={17} /></div><strong>{audit.length}</strong><p>{t.eventsHint}</p></article><article className="stat-card"><div className="stat-top"><span>{t.recording}</span><Icon name="shield" size={17} /></div><strong>{compliance.recording_allowed ? "ON" : "OFF"}</strong><p>{compliance.recording_allowed ? t.recordingOn : t.recordingOff}</p></article></section>
    <section className="lower-grid"><article className="panel activity-panel"><div className="panel-heading"><div><p className="eyebrow">{t.activity}</p><h3>{audit.length ? `${audit.length} ${language === "es" ? "registros locales" : "local records"}` : t.noActivity}</h3></div><Icon name="activity" size={20} /></div>{audit.length ? <div className="audit-list">{audit.slice(-4).reverse().map((entry, index) => <div className="audit-row" key={`${entry.created_at}-${index}`}><span className="audit-marker" /><div><strong>{entry.action} · {entry.entity}</strong><small>{new Date(entry.created_at).toLocaleString(language === "es" ? "es-ES" : "en-US")}</small></div></div>)}</div> : <div className="empty-activity"><div className="empty-line" /><p>{t.auditHint}</p></div>}</article><article className="panel protected-panel"><div className="shield-backdrop"><Icon name="shield" size={96} /></div><div className="panel-heading"><div><p className="eyebrow">{t.access}</p><h3>{t.protected}</h3></div><Icon name="lock" size={20} /></div><p>{t.protectedHint}</p><div className="access-row"><span className="signal-dot" />{t.localOnly}<Icon name="check" size={16} /></div><button className="secondary-button" onClick={() => setRoute("settings")}>{t.configure}<Icon name="chevron" size={15} /></button></article></section>
  </div>;
}

function Reserved({ language, route, setRoute }: { language: Language; route: RouteKey; setRoute: (route: RouteKey) => void }) {
  const t = copy[language]; const label = t.nav[route];
  return <div className="page-content reserved-page"><div className="reserved-mark"><Icon name={route === "cameras" ? "camera" : route === "map" ? "globe" : route === "alerts" ? "alert" : "settings"} size={32} /></div><p className="eyebrow">{label}</p><h1>{t.moduleReserved}</h1><p className="lede">{t.moduleHint}</p><button className="secondary-button" onClick={() => setRoute("summary")}>{t.backSummary}<Icon name="arrow" size={16} /></button></div>;
}

function Shell({ language, onLanguage, onLogout }: { language: Language; onLanguage: () => void; onLogout: () => void }) {
  const t = copy[language];
  const [route, setRouteState] = useState<RouteKey>(() => (window.location.pathname.slice(1) as RouteKey) || "summary");
  const [compact, setCompact] = useState(false);
  const [dark, setDark] = useState(true);
  const [compliance, setCompliance] = useState<Compliance>({ signage_confirmed: false, mandate_confirmed: false, kill_switch: false, recording_allowed: false, updated_at: "" });
  const [cameras, setCameras] = useState<Camera[]>([]); const [audit, setAudit] = useState<AuditEntry[]>([]); const [demo, setDemo] = useState(false);
  const setRoute = (next: RouteKey) => { setRouteState(next); window.history.pushState({}, "", next === "summary" ? "/" : `/${next}`); };
  useEffect(() => { document.documentElement.dataset.theme = dark ? "dark" : "light"; }, [dark]);
  useEffect(() => { const pop = () => setRouteState((window.location.pathname.slice(1) as RouteKey) || "summary"); window.addEventListener("popstate", pop); return () => window.removeEventListener("popstate", pop); }, []);
  useEffect(() => { Promise.all([api<Compliance>("/api/compliance"), api<{ items: Camera[] }>("/api/cameras"), api<{ items: AuditEntry[] }>("/api/audit")]).then(([state, cams, logs]) => { setCompliance(state); setCameras(cams.items); setAudit(logs.items); }).catch(() => setDemo(true)); }, []);
  const routePage = useMemo(() => route === "summary" ? <Summary language={language} compliance={compliance} cameras={cameras} audit={audit} demo={demo} setRoute={setRoute} /> : <Reserved language={language} route={route} setRoute={setRoute} />, [route, language, compliance, cameras, audit, demo]);
  return <div className="app-shell"><Nav route={route} setRoute={setRoute} language={language} compact={compact} /><div className="main-area"><header className="topbar"><button className="icon-button mobile-menu" onClick={() => setCompact(!compact)} aria-label="Mostrar navegación"><Icon name="menu" size={20} /></button><div className="breadcrumb"><span>CONTROL /</span><strong>{t.nav[route]}</strong></div><div className="top-actions"><button className="mode-button" onClick={() => setDark(!dark)} aria-label={`${t.theme}: ${dark ? t.dark : t.light}`}>{dark ? <Icon name="moon" size={16} /> : <Icon name="sun" size={16} />}<span>{dark ? t.dark : t.light}</span></button><button className="language-button" onClick={onLanguage}>{language.toUpperCase()}<Icon name="globe" size={14} /></button><button className="profile-button" onClick={onLogout}><span className="avatar">OP</span><span className="profile-name">{t.signOut}</span><Icon name="logout" size={15} /></button></div></header><main>{routePage}</main></div></div>;
}

export default function App() {
  const [language, setLanguage] = useState<Language>(() => (localStorage.getItem("perimetral-language") as Language) || "es");
  const [authenticated, setAuthenticated] = useState(() => sessionStorage.getItem("perimetral-auth") === "1");
  const onLanguage = () => { const next = language === "es" ? "en" : "es"; setLanguage(next); localStorage.setItem("perimetral-language", next); };
  const onLogout = async () => { try { await api("/api/auth/logout", { method: "POST" }); } catch { /* API may be offline in preview. */ } sessionStorage.removeItem("perimetral-auth"); setAuthenticated(false); };
  return authenticated ? <Shell language={language} onLanguage={onLanguage} onLogout={onLogout} /> : <Login language={language} onLanguage={onLanguage} onLoggedIn={() => setAuthenticated(true)} />;
}
