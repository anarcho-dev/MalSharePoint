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
          'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all',
          isActive
            ? 'bg-red-600/15 text-red-400 border border-red-600/25'
            : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/70'
        )
      }
    >
      <Icon size={15} />
      {label}
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

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 flex flex-col bg-slate-900 border-r border-slate-800">
        {/* Brand */}
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-slate-800">
          <div className="w-7 h-7 rounded-lg bg-red-600/20 border border-red-600/40 flex items-center justify-center">
            <Shield size={14} className="text-red-400" />
          </div>
          <span className="font-semibold text-slate-100 tracking-tight text-sm">
            MalSharePoint
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-0.5">
          <p className="px-3 pt-1 pb-2 text-[10px] font-semibold text-slate-600 uppercase tracking-widest">
            Main
          </p>
          {mainNav.map((item) => (
            <SideNavLink key={item.to} {...item} />
          ))}

          {isAdmin() && (
            <>
              <p className="px-3 pt-5 pb-2 text-[10px] font-semibold text-slate-600 uppercase tracking-widest">
                Administration
              </p>
              {adminNav.map((item) => (
                <SideNavLink key={item.to} {...item} exact={item.to === '/admin'} />
              ))}
            </>
          )}
        </nav>

        {/* User section */}
        <div className="border-t border-slate-800 p-3">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-full bg-red-600/20 border border-red-600/30 flex items-center justify-center flex-shrink-0">
              <span className="text-[11px] font-bold text-red-400 uppercase">
                {user?.username?.[0] ?? '?'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-100 truncate">{user?.username}</p>
              <p className="text-[10px] text-slate-500 capitalize">{user?.role}</p>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded text-slate-600 hover:text-red-400 hover:bg-slate-800 transition-colors"
              title="Sign out"
            >
              <LogOut size={13} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        {user?.must_change_password && (
          <div className="mx-8 mt-6 px-4 py-3 rounded-xl bg-yellow-500/5 border border-yellow-500/20 flex items-center gap-3">
            <KeyRound size={15} className="text-yellow-400 flex-shrink-0" />
            <p className="text-sm text-yellow-300/80 flex-1">
              You are using the default password. Please{' '}
              <Link to="/change-password" className="underline hover:text-yellow-200">
                change it
              </Link>{' '}
              for security.
            </p>
          </div>
        )}
        <div className="p-8 max-w-6xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
