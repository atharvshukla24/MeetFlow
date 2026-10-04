import React from 'react';

export default function EmptyState({ icon: Icon, title, description, actionText, onAction }) {
  return (
    <div className="text-center py-16 px-4 bg-white border border-slate-200 rounded-lg">
      {Icon && (
        <div className="w-12 h-12 mx-auto rounded-full bg-slate-100 flex items-center justify-center text-slate-500 mb-3 border border-slate-200">
          <Icon className="w-6 h-6" />
        </div>
      )}
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      {description && <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">{description}</p>}
      {actionText && onAction && (
        <div className="mt-4">
          <button
            onClick={onAction}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 transition-colors shadow-xs"
          >
            {actionText}
          </button>
        </div>
      )}
    </div>
  );
}
