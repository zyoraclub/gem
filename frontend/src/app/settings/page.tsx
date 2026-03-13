"use client";

import { useState, useEffect } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface MonitorStatus {
  running: boolean;
  interval_seconds: number;
  interval_human: string;
  last_check: string | null;
  last_result: {
    checked_at?: string;
    total_products?: number;
    prices_checked?: number;
    prices_changed?: number;
    prices_dropped?: number;
    prices_increased?: number;
    errors?: number;
    changes?: Array<{
      name: string;
      old_price: number;
      new_price: number;
      change_percent: number;
      direction: string;
    }>;
  };
}

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    scrapeInterval: "24",
    priceAlertThreshold: "5",
    autoSync: true,
    notifyOnPriceChange: true,
    notifyOnError: true,
  });

  // Price Monitor state
  const [monitorStatus, setMonitorStatus] = useState<MonitorStatus | null>(null);
  const [intervalMinutes, setIntervalMinutes] = useState("60");
  const [monitorLoading, setMonitorLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [checkingNow, setCheckingNow] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Load monitor status on mount
  useEffect(() => {
    loadMonitorStatus();
    const interval = setInterval(loadMonitorStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadMonitorStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/monitor/status`);
      if (res.ok) {
        const data = await res.json();
        setMonitorStatus(data);
        if (data.interval_seconds) {
          setIntervalMinutes(String(Math.round(data.interval_seconds / 60)));
        }
      }
    } catch (e) {
      console.error("Failed to load monitor status:", e);
    } finally {
      setMonitorLoading(false);
    }
  };

  const startMonitor = async () => {
    setActionLoading(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/monitor/start?interval_minutes=${intervalMinutes}`, {
        method: "POST"
      });
      const data = await res.json();
      if (res.ok) {
        setMessage({ type: "success", text: data.message });
        loadMonitorStatus();
      } else {
        setMessage({ type: "error", text: data.detail || "Failed to start monitor" });
      }
    } catch (e) {
      setMessage({ type: "error", text: "Connection error" });
    } finally {
      setActionLoading(false);
    }
  };

  const stopMonitor = async () => {
    setActionLoading(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/monitor/stop`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setMessage({ type: "success", text: data.message });
        loadMonitorStatus();
      } else {
        setMessage({ type: "error", text: data.detail || "Failed to stop monitor" });
      }
    } catch (e) {
      setMessage({ type: "error", text: "Connection error" });
    } finally {
      setActionLoading(false);
    }
  };

  const checkNow = async () => {
    setCheckingNow(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/monitor/check-now`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setMessage({ type: "success", text: data.message });
        loadMonitorStatus();
      } else {
        setMessage({ type: "error", text: data.detail || "Failed to check prices" });
      }
    } catch (e) {
      setMessage({ type: "error", text: "Connection error" });
    } finally {
      setCheckingNow(false);
    }
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-black">Settings</h1>
        <p className="text-gray-500 mt-1">Configure your automation preferences</p>
      </div>

      {/* Status Message */}
      {message && (
        <div className={`mb-6 p-4 rounded-lg max-w-2xl ${message.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
          {message.text}
        </div>
      )}

      <div className="max-w-2xl space-y-6">
        {/* Price Monitor Section - NEW */}
        <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-black">Price Monitoring</h2>
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              monitorStatus?.running 
                ? "bg-green-100 text-green-700" 
                : "bg-gray-100 text-gray-600"
            }`}>
              {monitorLoading ? "Loading..." : monitorStatus?.running ? "Running" : "Stopped"}
            </span>
          </div>
          
          <p className="text-sm text-gray-600 mb-4">
            Automatically check prices of scraped products and update Google Sheet when prices change.
          </p>

          {/* Monitor Stats */}
          {monitorStatus?.last_check && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 p-3 bg-gray-50 rounded-lg text-sm">
              <div>
                <p className="text-xs text-gray-500">Last Check</p>
                <p className="font-medium">{new Date(monitorStatus.last_check).toLocaleTimeString()}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Checked</p>
                <p className="font-medium">{monitorStatus.last_result?.prices_checked || 0}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Changed</p>
                <p className="font-medium text-orange-600">{monitorStatus.last_result?.prices_changed || 0}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Errors</p>
                <p className="font-medium text-red-600">{monitorStatus.last_result?.errors || 0}</p>
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">Interval (minutes)</label>
              <input
                type="number"
                value={intervalMinutes}
                onChange={(e) => setIntervalMinutes(e.target.value)}
                min="5"
                max="1440"
                disabled={monitorStatus?.running}
                className="w-full px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black disabled:bg-gray-100"
              />
            </div>
            {monitorStatus?.running ? (
              <button
                onClick={stopMonitor}
                disabled={actionLoading}
                className="px-4 py-2 text-sm font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 disabled:opacity-50"
              >
                {actionLoading ? "..." : "Stop"}
              </button>
            ) : (
              <button
                onClick={startMonitor}
                disabled={actionLoading}
                className="px-4 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 disabled:opacity-50"
              >
                {actionLoading ? "..." : "Start"}
              </button>
            )}
            <button
              onClick={checkNow}
              disabled={checkingNow}
              className="px-4 py-2 text-sm font-medium border border-[#e5e5e5] rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              {checkingNow ? "Checking..." : "Check Now"}
            </button>
          </div>
        </div>

        {/* Scraping Settings - ORIGINAL */}
        <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm p-6">
          <h2 className="text-lg font-semibold text-black mb-4">Scraping Settings</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Scrape Interval (hours)
              </label>
              <input
                type="number"
                value={settings.scrapeInterval}
                onChange={(e) => setSettings({ ...settings, scrapeInterval: e.target.value })}
                className="w-full px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
              <p className="text-xs text-gray-500 mt-1">
                How often to automatically scrape products for price changes
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Price Alert Threshold (%)
              </label>
              <input
                type="number"
                value={settings.priceAlertThreshold}
                onChange={(e) => setSettings({ ...settings, priceAlertThreshold: e.target.value })}
                className="w-full px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
              <p className="text-xs text-gray-500 mt-1">
                Minimum price change percentage to trigger an alert
              </p>
            </div>
          </div>
        </div>

        {/* Sync Settings - ORIGINAL */}
        <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm p-6">
          <h2 className="text-lg font-semibold text-black mb-4">Sync Settings</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-700">Auto-sync with Google Sheets</p>
                <p className="text-xs text-gray-500">Automatically update sheets when data changes</p>
              </div>
              <button
                onClick={() => setSettings({ ...settings, autoSync: !settings.autoSync })}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  settings.autoSync ? "bg-black" : "bg-gray-200"
                }`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    settings.autoSync ? "left-7" : "left-1"
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

        {/* Notification Settings - ORIGINAL */}
        <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm p-6">
          <h2 className="text-lg font-semibold text-black mb-4">Notifications</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-700">Price Change Alerts</p>
                <p className="text-xs text-gray-500">Get notified when prices change significantly</p>
              </div>
              <button
                onClick={() =>
                  setSettings({ ...settings, notifyOnPriceChange: !settings.notifyOnPriceChange })
                }
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  settings.notifyOnPriceChange ? "bg-black" : "bg-gray-200"
                }`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    settings.notifyOnPriceChange ? "left-7" : "left-1"
                  }`}
                />
              </button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-700">Error Notifications</p>
                <p className="text-xs text-gray-500">Get notified when scraping or sync errors occur</p>
              </div>
              <button
                onClick={() => setSettings({ ...settings, notifyOnError: !settings.notifyOnError })}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  settings.notifyOnError ? "bg-black" : "bg-gray-200"
                }`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    settings.notifyOnError ? "left-7" : "left-1"
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

        {/* Danger Zone - ORIGINAL */}
        <div className="bg-white rounded-xl border border-red-200 shadow-sm p-6">
          <h2 className="text-lg font-semibold text-red-600 mb-4">Danger Zone</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-700">Reset Daily Counters</p>
                <p className="text-xs text-gray-500">Reset all account daily upload counts to 0</p>
              </div>
              <button className="px-4 py-2 text-sm font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50">
                Reset
              </button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-700">Clear All Data</p>
                <p className="text-xs text-gray-500">Delete all scraped products and price history</p>
              </div>
              <button className="px-4 py-2 text-sm font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50">
                Clear
              </button>
            </div>
          </div>
        </div>

        {/* Save Button - ORIGINAL */}
        <div className="flex justify-end">
          <button className="px-6 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 transition-colors">
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}
