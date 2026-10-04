import React from 'react';
import { NavLink } from 'react-router-dom';
import { Video, CheckSquare, Settings } from 'lucide-react';

export default function Sidebar() {
  const navItems = [
    { to: '/', label: 'Meetings', icon: Video, exact: true },
    { to: '/actions', label: 'Actions', icon: CheckSquare },
    { to: '/settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-56 bg-white border-r border-slate-200 flex flex-col shrink-0 select-none">
      {/* Brand Header */}
      <div className="h-14 px-5 border-b border-slate-200 flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-md bg-blue-600 text-white flex items-center justify-center font-bold text-sm shadow-xs">
          M
        </div>
        <div className="flex flex-col">
          <span className="font-semibold text-slate-900 text-sm tracking-tight leading-none">MeetFlow</span>
          <span className="text-[10px] text-slate-400 leading-none mt-1">Workflow Engine</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="p-3 space-y-1 flex-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.exact}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
