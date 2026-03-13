"use client";

export default function AccountsPage() {
  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-black">Accounts</h1>
        <p className="text-gray-500 mt-1">Manage GEM portal accounts</p>
      </div>

      {/* Coming Soon */}
      <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm p-12 text-center">
        <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-black mb-2">Feature will be added soon</h2>
        <p className="text-gray-500 max-w-md mx-auto">
          Account management for multiple GEM portal accounts with rotation and daily limit tracking is coming in a future update.
        </p>
      </div>
    </div>
  );
}
