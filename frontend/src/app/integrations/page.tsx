"use client";

import { useEffect, useState } from "react";
import {
  getGmailStatus,
  getSheetsStatus,
  connectGmail,
  connectSheets,
  disconnectSheets,
  getConnectedSheets,
  getGmailImapSettings,
  saveGmailImapSettings,
  testGmailImap,
  GmailStatus,
  SheetsStatus,
  ConnectedSheet,
  GmailImapSettings,
} from "@/lib/api";

function IntegrationCard({
  title,
  description,
  icon,
  connected,
  email,
  onConnect,
  onDisconnect,
  loading,
}: {
  title: string;
  description: string;
  icon: React.ReactNode;
  connected: boolean;
  email?: string;
  onConnect: () => void;
  onDisconnect: () => void;
  loading: boolean;
}) {
  return (
    <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm p-6">
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 bg-black rounded-lg flex items-center justify-center flex-shrink-0">
          {icon}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold text-black">{title}</h3>
            <span
              className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                connected
                  ? "bg-green-100 text-green-700"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              {connected ? "Connected" : "Not Connected"}
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-1">{description}</p>
          {connected && email && (
            <p className="text-sm text-gray-600 mt-2">
              Connected as: <span className="font-medium">{email}</span>
            </p>
          )}
        </div>
      </div>
      <div className="mt-4 pt-4 border-t border-[#e5e5e5]">
        {connected ? (
          <button
            onClick={onDisconnect}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            Disconnect
          </button>
        ) : (
          <button
            onClick={onConnect}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
          >
            {loading ? "Connecting..." : "Connect"}
          </button>
        )}
      </div>
    </div>
  );
}

function ConnectedSheetsTable({ sheets }: { sheets: ConnectedSheet[] }) {
  if (!sheets || sheets.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No sheets connected yet. Connect Google Sheets first, then add spreadsheets.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[#e5e5e5]">
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Spreadsheet</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Sheet</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Connected</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Actions</th>
          </tr>
        </thead>
        <tbody>
          {sheets.map((sheet) => (
            <tr key={sheet.id} className="border-b border-[#e5e5e5] last:border-0">
              <td className="py-3 px-4 text-sm text-black font-medium">{sheet.spreadsheet_name || sheet.name}</td>
              <td className="py-3 px-4 text-sm text-gray-600">{sheet.sheet_name || "Sheet1"}</td>
              <td className="py-3 px-4 text-sm text-gray-500">
                {sheet.connected_at ? new Date(sheet.connected_at).toLocaleDateString() : sheet.last_synced_at ? new Date(sheet.last_synced_at).toLocaleDateString() : "-"}
              </td>
              <td className="py-3 px-4 text-right">
                <button className="text-sm text-gray-500 hover:text-black">
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function IntegrationsPage() {
  const [gmailStatus, setGmailStatus] = useState<GmailStatus>({ connected: false });
  const [sheetsStatus, setSheetsStatus] = useState<SheetsStatus>({ connected: false });
  const [connectedSheets, setConnectedSheets] = useState<ConnectedSheet[]>([]);
  const [loading, setLoading] = useState({ gmail: false, sheets: false });
  
  // Gmail IMAP settings
  const [imapSettings, setImapSettings] = useState<GmailImapSettings | null>(null);
  const [imapForm, setImapForm] = useState({
    email: "",
    app_password: "",
    imap_server: "imap.gmail.com",
    imap_port: 993,
  });
  const [imapSaving, setImapSaving] = useState(false);
  const [imapTesting, setImapTesting] = useState(false);
  const [imapMessage, setImapMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    loadStatuses();
    loadImapSettings();
  }, []);

  async function loadImapSettings() {
    try {
      const settings = await getGmailImapSettings();
      setImapSettings(settings);
      setImapForm({
        email: settings.email || "",
        app_password: "",
        imap_server: settings.imap_server || "imap.gmail.com",
        imap_port: settings.imap_port || 993,
      });
    } catch (e) {
      console.error("Failed to load IMAP settings:", e);
    }
  }

  async function loadStatuses() {
    const [gmail, sheets, connected] = await Promise.all([
      getGmailStatus(),
      getSheetsStatus(),
      getConnectedSheets(),
    ]);
    setGmailStatus(gmail);
    setSheetsStatus(sheets);
    setConnectedSheets(Array.isArray(connected) ? connected : []);
  }

  async function handleConnectGmail() {
    setLoading((prev) => ({ ...prev, gmail: true }));
    try {
      const { auth_url } = await connectGmail();
      window.location.href = auth_url;
    } catch (error) {
      console.error("Failed to connect Gmail:", error);
      alert("Failed to initiate Gmail connection. Make sure the backend is running.");
    } finally {
      setLoading((prev) => ({ ...prev, gmail: false }));
    }
  }

  async function handleConnectSheets() {
    setLoading((prev) => ({ ...prev, sheets: true }));
    try {
      const { auth_url } = await connectSheets();
      window.location.href = auth_url;
    } catch (error) {
      console.error("Failed to connect Sheets:", error);
      alert("Failed to initiate Sheets connection. Make sure the backend is running.");
    } finally {
      setLoading((prev) => ({ ...prev, sheets: false }));
    }
  }

  async function handleDisconnectSheets() {
    if (!confirm("Are you sure you want to disconnect Google Sheets?")) return;
    setLoading((prev) => ({ ...prev, sheets: true }));
    try {
      await disconnectSheets();
      setSheetsStatus({ connected: false, email: undefined });
      setConnectedSheets([]);
    } catch (error) {
      console.error("Failed to disconnect Sheets:", error);
      alert("Failed to disconnect Google Sheets.");
    } finally {
      setLoading((prev) => ({ ...prev, sheets: false }));
    }
  }

  async function handleSaveImap() {
    if (!imapForm.email || !imapForm.app_password) {
      setImapMessage({ type: "error", text: "Email and App Password are required" });
      return;
    }
    setImapSaving(true);
    setImapMessage(null);
    try {
      await saveGmailImapSettings(imapForm);
      setImapMessage({ type: "success", text: "Gmail IMAP settings saved successfully" });
      await loadImapSettings();
    } catch (error) {
      setImapMessage({ type: "error", text: "Failed to save settings" });
    } finally {
      setImapSaving(false);
    }
  }

  async function handleTestImap() {
    setImapTesting(true);
    setImapMessage(null);
    try {
      const result = await testGmailImap();
      setImapMessage({
        type: result.success ? "success" : "error",
        text: result.message,
      });
    } catch (error) {
      setImapMessage({ type: "error", text: "Failed to test connection" });
    } finally {
      setImapTesting(false);
    }
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-black">Integrations</h1>
        <p className="text-gray-500 mt-1">Connect your Google services for automation.</p>
      </div>

      {/* Gmail IMAP Settings */}
      <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm p-6 mb-6">
        <div className="flex items-start gap-4 mb-4">
          <div className="w-12 h-12 bg-black rounded-lg flex items-center justify-center flex-shrink-0">
            <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
            </svg>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-black">Gmail IMAP</h3>
              <span
                className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                  imapSettings?.configured
                    ? "bg-green-100 text-green-700"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {imapSettings?.configured ? "Configured" : "Not Configured"}
              </span>
            </div>
            <p className="text-sm text-gray-500 mt-1">
              Configure Gmail IMAP to read OTP codes from GEM Portal emails
            </p>
          </div>
        </div>

        {/* IMAP Form */}
        <div className="space-y-4 pt-4 border-t border-[#e5e5e5]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Gmail Email</label>
              <input
                type="email"
                value={imapForm.email}
                onChange={(e) => setImapForm({ ...imapForm, email: e.target.value })}
                placeholder="your-email@gmail.com"
                className="w-full px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                App Password
                <a
                  href="https://myaccount.google.com/apppasswords"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-2 text-blue-600 hover:underline text-xs"
                >
                  (Get App Password)
                </a>
              </label>
              <input
                type="password"
                value={imapForm.app_password}
                onChange={(e) => setImapForm({ ...imapForm, app_password: e.target.value })}
                placeholder={imapSettings?.has_password ? "••••••••••••••••" : "Enter app password"}
                className="w-full px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">IMAP Server</label>
              <input
                type="text"
                value={imapForm.imap_server}
                onChange={(e) => setImapForm({ ...imapForm, imap_server: e.target.value })}
                placeholder="imap.gmail.com"
                className="w-full px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">IMAP Port</label>
              <input
                type="number"
                value={imapForm.imap_port}
                onChange={(e) => setImapForm({ ...imapForm, imap_port: parseInt(e.target.value) || 993 })}
                placeholder="993"
                className="w-full px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
          </div>

          {imapMessage && (
            <div
              className={`p-3 rounded-lg text-sm ${
                imapMessage.type === "success"
                  ? "bg-green-50 text-green-700 border border-green-200"
                  : "bg-red-50 text-red-700 border border-red-200"
              }`}
            >
              {imapMessage.text}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleSaveImap}
              disabled={imapSaving}
              className="px-4 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 disabled:opacity-50"
            >
              {imapSaving ? "Saving..." : "Save Settings"}
            </button>
            <button
              onClick={handleTestImap}
              disabled={imapTesting || !imapSettings?.configured}
              className="px-4 py-2 text-sm font-medium border border-black rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              {imapTesting ? "Testing..." : "Test Connection"}
            </button>
          </div>

          <p className="text-xs text-gray-500">
            Note: You need to enable 2-Step Verification in your Google account and create an App Password for IMAP access.
          </p>
        </div>
      </div>

      {/* Google Sheets Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <IntegrationCard
          title="Google Sheets"
          description="Sync product data and price changes to Google Sheets"
          icon={
            <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14zM7 10h2v7H7zm4-3h2v10h-2zm4 6h2v4h-2z" />
            </svg>
          }
          connected={sheetsStatus.connected}
          email={sheetsStatus.email}
          onConnect={handleConnectSheets}
          onDisconnect={handleDisconnectSheets}
          loading={loading.sheets}
        />
      </div>

      {/* 2Captcha Integration */}
      <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm p-6 mb-8">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 bg-black rounded-lg flex items-center justify-center flex-shrink-0">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-black">2Captcha API</h3>
            <p className="text-sm text-gray-500 mt-1">
              Automatically solve captchas during GEM portal login
            </p>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-[#e5e5e5]">
          <label className="block text-sm font-medium text-gray-700 mb-2">API Key</label>
          <div className="flex gap-3">
            <input
              type="password"
              placeholder="Enter your 2Captcha API key"
              className="flex-1 px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
            />
            <button className="px-4 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 transition-colors">
              Save
            </button>
          </div>
        </div>
      </div>

      {/* Connected Sheets */}
      <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm">
        <div className="p-6 border-b border-[#e5e5e5] flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-black">Connected Spreadsheets</h3>
            <p className="text-sm text-gray-500 mt-1">Manage your connected Google Sheets</p>
          </div>
          <button
            disabled={!sheetsStatus.connected}
            className="px-4 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Add Spreadsheet
          </button>
        </div>
        <div className="p-6">
          <ConnectedSheetsTable sheets={connectedSheets} />
        </div>
      </div>
    </div>
  );
}
