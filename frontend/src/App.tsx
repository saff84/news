import * as Dialog from "@radix-ui/react-dialog";
import { Activity, Bot, Building2, CalendarClock, FileText, LayoutTemplate, LineChart, LogOut, Map, Menu, MessageCircle, MessageSquare, MessageSquareMore, Newspaper, Rss, Users, Wrench, X } from "lucide-react";
import { Navigate, Route, Routes, Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "./state/auth";
import { LoginPage } from "./pages/LoginPage";
import { RegionsPage } from "./pages/RegionsPage";
import { CompetitorsPage } from "./pages/CompetitorsPage";
import { DevelopersPage } from "./pages/DevelopersPage";
import { SourcesPage } from "./pages/SourcesPage";
import { ParsingTemplatesPage } from "./pages/ParsingTemplatesPage";
import { MonitoringPage } from "./pages/MonitoringPage";
import { CrawlSchedulePage } from "./pages/CrawlSchedulePage";
import { DiagnosticsPage } from "./pages/DiagnosticsPage";
import { IndicatorsPage } from "./pages/IndicatorsPage";
import { TelegramParserPage } from "./pages/TelegramParserPage";
import { MaxParserPage } from "./pages/MaxParserPage";
import { VkParserPage } from "./pages/VkParserPage";
import { NewsPage } from "./pages/NewsPage";
import { ReportConfigPage } from "./pages/ReportConfigPage";
import { AIConfigPage } from "./pages/AIConfigPage";

function MenuLink({
  to,
  icon,
  children,
  onClick,
}: {
  to: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      className={({ isActive }) =>
        `flex items-center gap-2 rounded px-3 py-2 text-sm transition ${
          isActive ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"
        }`
      }
    >
      <span className="shrink-0 opacity-90">{icon}</span>
      {children}
    </NavLink>
  );
}

function SidebarNav({ variant }: { variant?: "static" | "dialog" }) {
  const wrap = (node: React.ReactElement) => {
    if (variant !== "dialog") return node;
    return <Dialog.Close asChild>{node}</Dialog.Close>;
  };
  return (
    <nav className="grid gap-1 p-2">
      <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Разделы</div>
      {wrap(
        <MenuLink to="/regions" icon={<Map className="h-4 w-4" />}>
          Регионы
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/competitors" icon={<Users className="h-4 w-4" />}>
          Конкуренты
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/developers" icon={<Building2 className="h-4 w-4" />}>
          Застройщики
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/sources" icon={<Rss className="h-4 w-4" />}>
          Источники
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/parsing-templates" icon={<LayoutTemplate className="h-4 w-4" />}>
          Шаблоны (HTML)
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/news" icon={<Newspaper className="h-4 w-4" />}>
          Новости
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/monitoring" icon={<Activity className="h-4 w-4" />}>
          Мониторинг
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/indicators" icon={<LineChart className="h-4 w-4" />}>
          Индикаторы
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/report-config" icon={<FileText className="h-4 w-4" />}>
          Отчёт для PDF
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/ai-config" icon={<Bot className="h-4 w-4" />}>
          Подключение ИИ
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/telegram-parser" icon={<MessageCircle className="h-4 w-4" />}>
          Telegram-парсер
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/max-parser" icon={<MessageSquareMore className="h-4 w-4" />}>
          MAX-парсер
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/vk-parser" icon={<MessageSquare className="h-4 w-4" />}>
          VK-парсер
        </MenuLink>,
      )}
      {wrap(
        <MenuLink to="/diagnostics" icon={<Wrench className="h-4 w-4" />}>
          Диагностика
        </MenuLink>,
      )}
      <div className="mt-3 border-t px-3 py-2 text-xs text-slate-500">
        Изменения в конфигурации доступны только роли <b>Admin</b>.
      </div>
    </nav>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const title = (() => {
    if (loc.pathname.startsWith("/regions")) return "Регионы";
    if (loc.pathname.startsWith("/competitors")) return "Конкуренты";
    if (loc.pathname.startsWith("/developers")) return "Застройщики";
    if (loc.pathname.startsWith("/sources")) return "Источники";
    if (loc.pathname.startsWith("/parsing-templates")) return "Шаблоны парсинга";
    if (loc.pathname.startsWith("/news")) return "Новости";
    if (loc.pathname.startsWith("/crawl-schedule")) return "Планировка обхода";
    if (loc.pathname.startsWith("/monitoring")) return "Мониторинг";
    if (loc.pathname.startsWith("/indicators")) return "Индикаторы";
    if (loc.pathname.startsWith("/report-config")) return "Отчёт для PDF";
    if (loc.pathname.startsWith("/ai-config")) return "Подключение ИИ";
    if (loc.pathname.startsWith("/telegram-parser")) return "Telegram-парсер";
    if (loc.pathname.startsWith("/max-parser")) return "MAX-парсер";
    if (loc.pathname.startsWith("/vk-parser")) return "VK-парсер";
    if (loc.pathname.startsWith("/diagnostics")) return "Диагностика";
    return "Admin";
  })();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-40 border-b bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-screen-2xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Dialog.Root>
              <Dialog.Trigger asChild>
                <button className="inline-flex items-center justify-center rounded border bg-white p-2 hover:bg-slate-50 md:hidden" aria-label="Открыть меню">
                  <Menu className="h-4 w-4" />
                </button>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 bg-black/40" />
                <Dialog.Content className="fixed inset-y-0 left-0 w-[320px] max-w-[85vw] overflow-y-auto bg-white shadow-xl">
                  <div className="flex items-center justify-between border-b px-4 py-3">
                    <div className="text-sm font-semibold">Меню</div>
                    <Dialog.Close asChild>
                      <button className="rounded p-2 hover:bg-slate-50" aria-label="Закрыть меню">
                        <X className="h-4 w-4" />
                      </button>
                    </Dialog.Close>
                  </div>
                  <SidebarNav variant="dialog" />
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>

            <Link to="/" className="font-semibold">
              NewsInt Admin
            </Link>
            <span className="hidden text-sm text-slate-600 md:inline">/ {title}</span>
          </div>

          <div className="flex items-center gap-2 text-sm">
            {user ? (
              <>
                <div className="hidden items-center gap-2 rounded border bg-white px-3 py-1.5 md:flex">
                  <span className="text-slate-700">{user.email}</span>
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{user.role}</span>
                </div>
                <button
                  className="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
                  onClick={() => {
                    logout();
                    nav("/login");
                  }}
                >
                  <LogOut className="h-4 w-4" />
                  <span className="hidden sm:inline">Выйти</span>
                </button>
              </>
            ) : null}
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-screen-2xl grid-cols-1 gap-6 px-4 py-6 sm:px-6 md:grid-cols-[280px_1fr]">
        <aside className="hidden h-fit rounded-lg border bg-white md:block">
          <SidebarNav variant="static" />
        </aside>
        <main className="min-w-0">{children}</main>
      </div>
    </div>
  );
}

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="text-sm text-slate-600">Загрузка…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Shell>
              <Navigate to="/regions" replace />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/regions"
        element={
          <RequireAuth>
            <Shell>
              <RegionsPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/competitors"
        element={
          <RequireAuth>
            <Shell>
              <CompetitorsPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/developers"
        element={
          <RequireAuth>
            <Shell>
              <DevelopersPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/sources"
        element={
          <RequireAuth>
            <Shell>
              <SourcesPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/parsing-templates"
        element={
          <RequireAuth>
            <Shell>
              <ParsingTemplatesPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/news"
        element={
          <RequireAuth>
            <Shell>
              <NewsPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/crawl-schedule"
        element={
          <RequireAuth>
            <Shell>
              <CrawlSchedulePage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/monitoring"
        element={
          <RequireAuth>
            <Shell>
              <MonitoringPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/telegram-parser"
        element={
          <RequireAuth>
            <Shell>
              <TelegramParserPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/max-parser"
        element={
          <RequireAuth>
            <Shell>
              <MaxParserPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/vk-parser"
        element={
          <RequireAuth>
            <Shell>
              <VkParserPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/diagnostics"
        element={
          <RequireAuth>
            <Shell>
              <DiagnosticsPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/indicators"
        element={
          <RequireAuth>
            <Shell>
              <IndicatorsPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/report-config"
        element={
          <RequireAuth>
            <Shell>
              <ReportConfigPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/ai-config"
        element={
          <RequireAuth>
            <Shell>
              <AIConfigPage />
            </Shell>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

