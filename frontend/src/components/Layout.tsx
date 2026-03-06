import { Outlet, NavLink, useNavigate, Link } from 'react-router-dom';
import {
  LayoutDashboard,
  FolderOpen,
  UploadCloud,
  Users,
  ScrollText,
  LogOut,
  Shield,
  KeyRound,
  Zap,
  Radio,
  AlertTriangle,
} from 'lucide-react';
import clsx from 'clsx';
import { useAuthStore } from '../store/authStore';

interface NavItem {
  to: string;
  label: string;
  Icon: React.ElementType;
}

const mainNav: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', Icon: LayoutDashboard },
  { to: '/files', label: 'Files', Icon: FolderOpen },
  { to: '/upload', label: 'Upload', Icon: UploadCloud },
  { to: '/payload-delivery', label: 'Payload Delivery', Icon: Zap },
  { to: '/listener', label: 'Listener', Icon: Radio },
];

const adminNav: NavItem[] = [
  { to: '/admin', label: 'Overview', Icon: LayoutDashboard },
  { to: '/admin/users', label: 'Users', Icon: Users },
  { to: '/admin/logs', label: 'Audit Logs', Icon: ScrollText },
];

function SideNavLink({ to, label, Icon, exact = false }: NavItem & { exact?: boolean }) {
  return (
    <NavLink
      to={to}
      end={exact}
      className={({ isActive }) =>
        clsx(
          'group relative flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200',
          isActive
            ? 'bg-gradient-to-r from-red-600/20 to-red-600/5 text-red-400 shadow-[inset_0_0_0_1px_rgba(220,38,38,0.25)]'
            : 'text-slate-500 hover:text-slate-200 hover:bg-slate-800/60'
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 bg-red-500 rounded-r-full shadow-[0_0_6px_rgba(239,68,68,0.8)]" />
          )}
          <Icon
            size={15}
            className={clsx(
              'transition-colors duration-200',
              isActive ? 'text-red-400' : 'text-slate-600 group-hover:text-slate-300'
            )}
          />
          {label}
        </>
      )}
    </NavLink>
  );
}

export default function Layout() {
  const { user, logout, isAdmin } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const roleBadge: Record<string, string> = {
    admin: 'text-red-400',
    user: 'text-blue-400',
    readonly: 'text-slate-400',
  };

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      {/* Sidebar */}
      <aside className="w-58 flex-shrink-0 flex flex-col bg-slate-900/95 border-r border-slate-800/80 backdrop-blur-sm"
             style={{ width: '224px' }}>
        {/* Brand header with glow */}
        <div className="relative flex items-center gap-3 px-4 py-4 border-b border-slate-800/80">
          <div className="relative w-8 h-8 rounded-xl bg-gradient-to-br from-red-600/30 to-red-800/20 border border-red-600/40 flex items-center justify-center shadow-[0_0_12px_rgba(220,38,38,0.2)]">
            <Shield size={15} className="text-red-400" />
          </div>
          <div className="flex-1 min-w-0">
            <span className="font-bold text-slate-100 tracking-tight text-sm block">
              MalSharePoint
            </span>
            <span className="text-[9px] font-semibold text-slate-600 uppercase tracking-widest">
              Payload Platform
            </span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-0.5">
          <p className="px-3 pt-2 pb-2 text-[9px] font-bold text-slate-700 uppercase tracking-[0.12em]">
            Navigation
          </p>
          {mainNav.map((item) => (
            <SideNavLink key={item.to} {...item} />
          ))}

          {isAdmin() && (
            <>
              <div className="my-3 glow-line" />
              <p className="px-3 pb-2 text-[9px] font-bold text-slate-700 uppercase tracking-[0.12em]">
                Administration
              </p>
              {adminNav.map((item) => (
                <SideNavLink key={item.to} {...item} exact={item.to === '/admin'} />
              ))}
            </>
          )}
        </nav>

        {/* User footer */}
        <div className="border-t border-slate-800/80 p-3">
          <div className="flex items-center gap-2.5 px-1">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-red-600/25 to-red-900/20 border border-red-600/30 flex items-center justify-center flex-shrink-0 shadow-[0_0_8px_rgba(220,38,38,0.15)]">
              <span className="text-[11px] font-black text-red-400 uppercase">
                {user?.username?.[0] ?? '?'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-200 truncate leading-tight">
                {user?.username}
              </p>
              <p className={clsx('text-[10px] font-medium capitalize leading-tight', roleBadge[user?.role ?? ''] ?? 'text-slate-500')}>
                {user?.role}
              </p>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-400/10 transition-all duration-200"
              title="Sign out"
            >
              <LogOut size={13} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content area */}
      <main className="flex-1 overflow-y-auto min-w-0">
        {user?.must_change_password && (
          <div className="mx-6 mt-5 px-4 py-3 rounded-xl bg-amber-500/8 border border-amber-500/25 flex items-center gap-3">
            <AlertTriangle size={15} className="text-amber-400 flex-shrink-0" />
            <p className="text-sm text-amber-300/90 flex-1">
              You are using the default password. Please{' '}
              <Link to="/change-password" className="font-semibold underline underline-offset-2 hover:text-amber-200 transition-colors">
                change it now
              </Link>{' '}
              to secure your account.
            </p>
          </div>
        )}
        <div className="p-7 max-w-6xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
