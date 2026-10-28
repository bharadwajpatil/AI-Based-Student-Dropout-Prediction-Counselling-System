import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Compass,
  Bell,
  Sun,
  Moon,
  LogOut,
  CheckCheck,
  GraduationCap,
  Users,
  HeartHandshake,
  BarChart3,
  Shield,
  BookOpen,
  ClipboardList,
  Bot,
  Calendar,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { notificationApi } from '../../api/notifications';
import type { NotificationItem } from '../../types';

export const Navbar: React.FC = () => {
  const { user, logout, hasRole } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return (
      localStorage.getItem('beacon_theme') === 'dark' ||
      (!('beacon_theme' in localStorage) &&
        window.matchMedia('(prefers-color-scheme: dark)').matches)
    );
  });

  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [showNotifDropdown, setShowNotifDropdown] = useState<boolean>(false);
  const [showUserDropdown, setShowUserDropdown] = useState<boolean>(false);

  const notifRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  // Sync dark mode class
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('beacon_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('beacon_theme', 'light');
    }
  }, [darkMode]);

  // Load notification count & recent alerts
  const fetchNotifications = useCallback(async () => {
    if (!user) return;
    try {
      const data = await notificationApi.getNotifications({ limit: 5 });
      setNotifications(data.notifications);
      setUnreadCount(data.unread_count);
    } catch {
      // Ignore background notification fetch errors
    }
  }, [user]);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 60000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotifDropdown(false);
      }
      if (userRef.current && !userRef.current.contains(e.target as Node)) {
        setShowUserDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleMarkAllRead = async () => {
    try {
      await notificationApi.markAllRead();
      setUnreadCount(0);
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    } catch (err) {
      console.error(err);
    }
  };

  const handleMarkOneRead = async (id: string) => {
    try {
      await notificationApi.markRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read: true } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (err) {
      console.error(err);
    }
  };

  const navLinks = [
    { name: 'Dashboard', path: '/', icon: <Compass className="w-4 h-4 mr-1.5" /> },
    {
      name: 'HODs',
      path: '/admin/hods',
      icon: <Shield className="w-4 h-4 mr-1.5" />,
      visible: hasRole('admin'),
    },
    {
      name: 'Subjects',
      path: '/hod/subjects',
      icon: <BookOpen className="w-4 h-4 mr-1.5" />,
      visible: hasRole(['hod', 'admin']),
    },
    {
      name: 'My Subjects',
      path: '/teacher/subjects',
      icon: <BookOpen className="w-4 h-4 mr-1.5" />,
      visible: hasRole('teacher'),
    },
    {
      name: 'Marks Entry',
      path: '/teacher/marks',
      icon: <ClipboardList className="w-4 h-4 mr-1.5" />,
      visible: hasRole(['teacher', 'hod']),
    },
    {
      name: 'Students',
      path: '/students',
      icon: <Users className="w-4 h-4 mr-1.5" />,
      visible: hasRole(['admin', 'hod', 'teacher']),
    },
    {
      name: 'Faculty',
      path: '/faculty',
      icon: <GraduationCap className="w-4 h-4 mr-1.5" />,
      visible: hasRole(['admin', 'hod']),
    },
    {
      name: 'Counselling',
      path: '/counselling',
      icon: <HeartHandshake className="w-4 h-4 mr-1.5" />,
      visible: hasRole(['admin', 'hod', 'teacher']),
    },
    {
      name: 'Analytics',
      path: '/analytics',
      icon: <BarChart3 className="w-4 h-4 mr-1.5" />,
      visible: hasRole(['admin', 'hod']),
    },
    // Student Links
    {
      name: 'My Performance',
      path: '/student/performance',
      icon: <BarChart3 className="w-4 h-4 mr-1.5" />,
      visible: hasRole('student'),
    },
    {
      name: 'My Marks',
      path: '/student/marks',
      icon: <BookOpen className="w-4 h-4 mr-1.5" />,
      visible: hasRole('student'),
    },
    {
      name: 'AI Counsellor',
      path: '/student/counselling',
      icon: <Bot className="w-4 h-4 mr-1.5" />,
      visible: hasRole('student'),
    },
    {
      name: 'Study Plan',
      path: '/student/study-plan',
      icon: <Calendar className="w-4 h-4 mr-1.5" />,
      visible: hasRole('student'),
    },
  ];

  return (
    <header className="sticky top-0 z-40 bg-white/90 dark:bg-charcoal-900/90 backdrop-blur border-b border-sand-200 dark:border-charcoal-800 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-8">
            <Link to="/" className="flex items-center space-x-3 group">
              <div className="w-10 h-10 rounded-xl bg-clay-500 text-white flex items-center justify-center shadow-soft group-hover:bg-clay-600 transition-all card-lift">
                <GraduationCap className="w-6 h-6" />
              </div>
              <div>
                <span className="font-display font-bold text-xl tracking-tight text-ink-900 dark:text-sand-100">
                  Beacon
                </span>
                <span className="hidden sm:inline-block ml-2 text-xs font-medium text-clay-500 bg-cream-100 dark:bg-charcoal-800 px-2 py-0.5 rounded-full border border-sand-200 dark:border-charcoal-700">
                  Early Warning
                </span>
              </div>
            </Link>

            {/* Desktop Navigation */}
            {user && (
              <nav className="hidden md:flex items-center space-x-1">
                {navLinks
                  .filter((link) => link.visible !== false)
                  .map((link) => {
                    const isActive = location.pathname === link.path;
                    return (
                      <Link
                        key={link.path}
                        to={link.path}
                        className={`inline-flex items-center px-3.5 py-2 rounded-xl text-sm font-medium transition-all ${
                          isActive
                            ? 'bg-cream-100 text-clay-600 dark:bg-charcoal-800 dark:text-clay-400 font-semibold shadow-soft'
                            : 'text-ink-700 dark:text-sand-300 hover:text-ink-900 hover:bg-sand-100 dark:hover:bg-charcoal-800'
                        }`}
                      >
                        {link.icon}
                        {link.name}
                      </Link>
                    );
                  })}
              </nav>
            )}
          </div>

          {/* Right Controls */}
          {user ? (
            <div className="flex items-center space-x-3">
              {/* Dark mode toggle */}
              <button
                onClick={() => setDarkMode(!darkMode)}
                className="p-2 rounded-xl text-ink-500 hover:text-ink-900 hover:bg-cream-100 dark:text-sand-300 dark:hover:text-sand-100 dark:hover:bg-charcoal-800 transition-colors"
                aria-label="Toggle dark mode"
              >
                {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>

              {/* Notification Bell */}
              <div className="relative" ref={notifRef}>
                <button
                  onClick={() => setShowNotifDropdown(!showNotifDropdown)}
                  className="relative p-2 rounded-xl text-ink-500 hover:text-ink-900 hover:bg-cream-100 dark:text-sand-300 dark:hover:text-sand-100 dark:hover:bg-charcoal-800 transition-colors"
                  aria-label="Notifications"
                >
                  <Bell className="w-5 h-5" />
                  {unreadCount > 0 && (
                    <span className="absolute top-1.5 right-1.5 flex h-4 min-w-[1rem] px-1 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white shadow-soft">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </button>

                {/* Notifications Dropdown */}
                {showNotifDropdown && (
                  <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white dark:bg-charcoal-850 shadow-lift border border-sand-200 dark:border-charcoal-700 py-3 z-50 animate-fade-up">
                    <div className="px-4 pb-2 border-b border-sand-200 dark:border-charcoal-700 flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="font-display font-semibold text-sm text-ink-900 dark:text-sand-100">
                          Notifications
                        </span>
                        {unreadCount > 0 && (
                          <span className="text-xs bg-rose-100 text-rose-600 px-2 py-0.5 rounded-full font-medium">
                            {unreadCount} new
                          </span>
                        )}
                      </div>
                      {unreadCount > 0 && (
                        <button
                          onClick={handleMarkAllRead}
                          className="text-xs text-clay-500 hover:text-clay-600 flex items-center font-medium"
                        >
                          <CheckCheck className="w-3.5 h-3.5 mr-1" /> Mark all read
                        </button>
                      )}
                    </div>

                    <div className="max-h-72 overflow-y-auto divide-y divide-sand-200 dark:divide-charcoal-800">
                      {notifications.length === 0 ? (
                        <div className="p-6 text-center text-xs text-ink-500 dark:text-sand-400">
                          No recent notifications
                        </div>
                      ) : (
                        notifications.map((n) => (
                          <div
                            key={n.id}
                            onClick={() => !n.read && handleMarkOneRead(n.id)}
                            className={`p-3.5 transition-colors cursor-pointer hover:bg-cream-50 dark:hover:bg-charcoal-800 ${
                              !n.read
                                ? 'bg-cream-100/60 dark:bg-charcoal-800/60'
                                : ''
                            }`}
                          >
                            <div className="flex items-start justify-between">
                              <p className="text-xs font-semibold text-ink-900 dark:text-sand-100">
                                {n.title}
                              </p>
                              <span className="text-[10px] text-ink-500 dark:text-sand-400 ml-2 whitespace-nowrap">
                                {new Date(n.created_at).toLocaleDateString([], {
                                  hour: '2-digit',
                                  minute: '2-digit',
                                })}
                              </span>
                            </div>
                            <p className="text-xs text-ink-700 dark:text-sand-300 mt-1 line-clamp-2 leading-relaxed">
                              {n.message}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* User Menu */}
              <div className="relative" ref={userRef}>
                <button
                  onClick={() => setShowUserDropdown(!showUserDropdown)}
                  className="flex items-center space-x-2.5 p-1.5 rounded-xl hover:bg-cream-100 dark:hover:bg-charcoal-800 transition-colors"
                >
                  <div className="w-8 h-8 rounded-lg bg-clay-100 dark:bg-clay-600/30 text-clay-600 dark:text-clay-400 flex items-center justify-center font-semibold text-xs border border-clay-200 dark:border-clay-500/20">
                    {user.first_name?.[0] || user.email[0].toUpperCase()}
                  </div>
                  <div className="hidden lg:block text-left">
                    <p className="text-xs font-semibold text-ink-900 dark:text-sand-100 leading-none">
                      {user.first_name ? `${user.first_name} ${user.last_name || ''}` : user.email.split('@')[0]}
                    </p>
                    <p className="text-[10px] text-ink-500 dark:text-sand-400 uppercase tracking-wider mt-0.5">
                      {user.role}
                    </p>
                  </div>
                </button>

                {/* User Dropdown */}
                {showUserDropdown && (
                  <div className="absolute right-0 mt-2 w-52 rounded-2xl bg-white dark:bg-charcoal-850 shadow-lift border border-sand-200 dark:border-charcoal-700 py-2 z-50 animate-fade-up">
                    <div className="px-4 py-2 border-b border-sand-200 dark:border-charcoal-700">
                      <p className="text-xs font-bold text-ink-900 dark:text-sand-100">
                        {user.first_name} {user.last_name}
                      </p>
                      <p className="text-[11px] text-ink-500 dark:text-sand-400 truncate">
                        {user.email}
                      </p>
                      <span className="mt-1 inline-block text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-sand-200 dark:bg-charcoal-700 text-ink-700 dark:text-sand-300">
                        {user.role}
                      </span>
                    </div>

                    <button
                      onClick={async () => {
                        await logout();
                        navigate('/login');
                      }}
                      className="w-full text-left px-4 py-2.5 text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-charcoal-800 flex items-center transition-colors font-medium"
                    >
                      <LogOut className="w-4 h-4 mr-2" /> Sign Out
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center space-x-3">
              <Link
                to="/login"
                className="text-sm font-semibold text-ink-700 dark:text-sand-300 hover:text-clay-500"
              >
                Log In
              </Link>
              <Link
                to="/register"
                className="px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white font-medium text-sm shadow-soft card-lift transition-all"
              >
                Get Started
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
