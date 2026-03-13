"use client";

import { useState, useEffect } from "react";
import { getSheetsStatus, listSpreadsheets } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Spreadsheet {
  id: string;
  name: string;
}

interface SheetRow {
  rowIndex: number;
  url: string;
  productId: string;
  name: string;
  price: string;
  unit: string;
  seller: string;
  category: string;
  status: "pending" | "filling" | "otp" | "done" | "error";
  lastUpdated?: string;
  prevPrice?: string;
  priceChanged?: string;
  message?: string;
}

interface AutomationLog {
  time: string;
  message: string;
  type: "info" | "success" | "error" | "otp";
}

export default function AutomationPage() {
  const [sheetsConnected, setSheetsConnected] = useState(false);
  const [spreadsheets, setSpreadsheets] = useState<Spreadsheet[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [sheetData, setSheetData] = useState<SheetRow[]>([]);
  const [loadingData, setLoadingData] = useState(false);
  const [automationRunning, setAutomationRunning] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [logs, setLogs] = useState<AutomationLog[]>([]);
  const [chromeConnected, setChromeConnected] = useState(false);
  const [checkingChrome, setCheckingChrome] = useState(false);
  const [runningAdd, setRunningAdd] = useState(false);
  const [runningUpdate, setRunningUpdate] = useState(false);
  const [stoppingAutomation, setStoppingAutomation] = useState(false);
  const [formDetected, setFormDetected] = useState<boolean | null>(null);
  const [formType, setFormType] = useState<string | null>(null);
  const [gemTabs, setGemTabs] = useState<{url: string, title: string}[]>([]);
  const [showChromeHelp, setShowChromeHelp] = useState(false);
  const [chromeCommand, setChromeCommand] = useState("");

  // Load sheets status
  useEffect(() => {
    const loadStatus = async () => {
      try {
        const status = await getSheetsStatus();
        setSheetsConnected(status.connected);
        if (status.connected) {
          const sheets = await listSpreadsheets();
          setSpreadsheets(sheets);
          if (sheets.length > 0) {
            setSelectedSheet(sheets[0].id);
          }
        }
      } catch (e) {
        console.error("Failed to load sheets:", e);
      } finally {
        setLoading(false);
      }
    };
    loadStatus();
    
    // Timeout fallback - stop loading after 10 seconds
    const timeout = setTimeout(() => setLoading(false), 10000);
    return () => clearTimeout(timeout);
  }, []);

  // Auto-refresh Chrome status every 5 seconds
  useEffect(() => {
    // Initial check
    checkChromeConnection();
    
    // Set up interval for auto-refresh
    const interval = setInterval(() => {
      if (!checkingChrome) {
        checkChromeConnection();
      }
    }, 5000);
    
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Check Chrome connection and GEM form status
  const checkChromeConnection = async () => {
    setCheckingChrome(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/gem/status`);
      if (res.ok) {
        const data = await res.json();
        setChromeConnected(data.chrome_connected);
        setFormDetected(data.form_detected);
        setFormType(data.form_type);
        setGemTabs(data.gem_tabs || []);
        
        // Log detailed status
        if (!data.chrome_connected) {
          addLog("Chrome not connected on port 9222", "error");
        } else if (data.form_detected) {
          addLog(`GEM ${data.form_type?.toUpperCase()} form detected`, "success");
        } else if (data.gem_tabs?.length > 0) {
          addLog(`GEM portal open (${data.gem_tabs.length} tab(s)), but no form detected. Open the product form.`, "info");
        } else {
          addLog("Chrome connected but no GEM tabs open. Open gem.gov.in", "info");
        }
      }
    } catch {
      setChromeConnected(false);
      setFormDetected(null);
      setFormType(null);
      setGemTabs([]);
      addLog("Failed to check Chrome connection", "error");
    } finally {
      setCheckingChrome(false);
    }
  };

  // Launch Chrome with debug mode
  const launchDebugChrome = async () => {
    addLog("Launching debug Chrome (separate instance)...", "info");
    
    try {
      // Get the command for this platform
      const res = await fetch(`${API_BASE_URL}/api/gem/chrome-command`);
      if (res.ok) {
        const data = await res.json();
        setChromeCommand(data.command);
        addLog(`Platform: ${data.platform}`, "info");
        
        // Try to launch Chrome via backend (opens NEW instance, doesn't close existing)
        const launchRes = await fetch(`${API_BASE_URL}/api/gem/launch-chrome`, { method: "POST" });
        if (launchRes.ok) {
          const launchData = await launchRes.json();
          addLog(`✅ ${launchData.message}`, "success");
          setShowChromeHelp(false);
          // Wait a bit and check connection
          setTimeout(checkChromeConnection, 3000);
        } else {
          const errData = await launchRes.json();
          addLog(`❌ ${errData.detail || "Failed to launch Chrome"}`, "error");
          setShowChromeHelp(true);
          addLog("Copy the command below and run it manually", "info");
        }
      } else {
        addLog("Could not detect platform. Try running Chrome manually.", "error");
        setShowChromeHelp(true);
      }
    } catch {
      addLog("Could not connect to server. Is the backend running?", "error");
    }
  };

  // Run gem_add.py - Add NEW products to GEM portal
  const runAddProducts = async () => {
    setRunningAdd(true);
    setStoppingAutomation(false);
    addLog("Starting Add Products (gem_add.py)...", "info");
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/gem/add-products`, {
        method: "POST"
      });
      
      if (res.ok) {
        const data = await res.json();
        addLog(data.message, "success");
        setChromeConnected(true);
      } else {
        const err = await res.json();
        addLog(err.detail || "Failed to start Add Products", "error");
      }
    } catch (e) {
      addLog("Error connecting to server", "error");
    } finally {
      setRunningAdd(false);
    }
  };

  // Run gem_master.py - Update ACTIVE products on GEM portal
  const runUpdateProducts = async () => {
    setRunningUpdate(true);
    setStoppingAutomation(false);
    addLog("Starting Update Products (gem_master.py)...", "info");
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/gem/update-products`, {
        method: "POST"
      });
      
      if (res.ok) {
        const data = await res.json();
        addLog(data.message, "success");
        setChromeConnected(true);
      } else {
        const err = await res.json();
        addLog(err.detail || "Failed to start Update Products", "error");
      }
    } catch (e) {
      addLog("Error connecting to server", "error");
    } finally {
      setRunningUpdate(false);
    }
  };

  // Stop running automation
  const stopRunningAutomation = async () => {
    setStoppingAutomation(true);
    addLog("Sending stop signal...", "info");
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/gem/stop-automation`, {
        method: "POST"
      });
      
      if (res.ok) {
        const data = await res.json();
        addLog(data.message, "success");
        setRunningAdd(false);
        setRunningUpdate(false);
      } else {
        const err = await res.json();
        addLog(err.detail || "Failed to stop automation", "error");
      }
    } catch (e) {
      addLog("Error sending stop signal", "error");
    } finally {
      setStoppingAutomation(false);
    }
  };

  // Load data from selected sheet
  const loadSheetData = async () => {
    if (!selectedSheet) {
      addLog("Please select a sheet", "error");
      return;
    }
    setLoadingData(true);
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/sheets/${selectedSheet}/read?range=A:M`);
      if (res.ok) {
        const result = await res.json();
        const rows = result.data || [];
        
        // Parse rows - Column C ONLY for status
        // A(0): URL, B(1): Product ID, C(2): Status (NEW/ADD/DONE)
        // E(4): Price, G(6): Seller, H(7): Full URL
        if (rows.length > 0) {
          const parsedData: SheetRow[] = rows
            .filter((row: string[]) => row[0] && row[0].trim()) // Has URL in column A
            .map((row: string[], idx: number) => {
              const statusCol = (row[2] || "").trim().toUpperCase(); // Column C = Status
              return {
                rowIndex: idx + 1,
                url: row[0] || "",
                productId: row[1] || "",
                name: row[1] || "", // Use ID as name placeholder
                price: row[4] || "",
                status: (statusCol === "DONE" ? "done" : "pending") as SheetRow["status"], // Column C = DONE means processed
                unit: "",
                seller: row[6] || "",
                category: "",
                lastUpdated: "",
                prevPrice: "",
                priceChanged: statusCol, // Column C = Status (NEW/ADD) - normalized
                message: statusCol === "ADD" ? "Add product" : (statusCol === "NEW" ? "New product" : ""),
              };
            });
          setSheetData(parsedData);
          const newCount = parsedData.filter(r => r.priceChanged === "NEW" || r.priceChanged === "ADD").length;
          const changedCount = 0; // No price change tracking in this format
          addLog(`Loaded ${parsedData.length} products (${newCount} new, ${changedCount} price changes)`, "success");
        } else {
          setSheetData([]);
          addLog("Sheet is empty", "info");
        }
      } else {
        addLog("Failed to read sheet data", "error");
      }
    } catch (e) {
      console.error("Failed to load sheet data:", e);
      addLog("Error connecting to server", "error");
    } finally {
      setLoadingData(false);
    }
  };

  // Auto-load when sheet changes
  useEffect(() => {
    if (selectedSheet && sheetsConnected) {
      loadSheetData();
    }
  }, [selectedSheet, sheetsConnected]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    if (!selectedSheet || !sheetsConnected) return;
    
    const interval = setInterval(() => {
      loadSheetData();
    }, 30000);
    
    return () => clearInterval(interval);
  }, [selectedSheet, sheetsConnected]);

  // Add log entry
  const addLog = (message: string, type: AutomationLog["type"] = "info") => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { time, message, type }]);
  };

  // Run automation for a single row
  const runSingleAutomation = async (index: number) => {
    const row = sheetData[index];
    if (!row) return;

    setSheetData((prev) =>
      prev.map((r, i) => (i === index ? { ...r, status: "filling" } : r))
    );
    addLog(`Processing: ${row.name}`, "info");

    try {
      const res = await fetch(`${API_BASE_URL}/api/automation/fill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_name: row.name,
          price: row.price,
          unit: row.unit,
          seller: row.seller,
          product_id: row.productId,
          category: row.category,
        }),
      });

      if (res.ok) {
        const result = await res.json();
        
        if (result.needs_otp) {
          setSheetData((prev) =>
            prev.map((r, i) => (i === index ? { ...r, status: "otp" } : r))
          );
          addLog("Waiting for OTP...", "otp");
          
          // Wait for OTP
          const otpRes = await fetch(`${API_BASE_URL}/api/automation/wait-otp`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ timeout: 120 }),
          });
          
          if (otpRes.ok) {
            const otpResult = await otpRes.json();
            if (otpResult.success) {
              addLog(`OTP received and submitted: ${otpResult.otp}`, "success");
              setSheetData((prev) =>
                prev.map((r, i) => (i === index ? { ...r, status: "done", message: "Completed" } : r))
              );
            } else {
              throw new Error(otpResult.message || "OTP failed");
            }
          } else {
            throw new Error("OTP timeout");
          }
        } else if (result.success) {
          setSheetData((prev) =>
            prev.map((r, i) => (i === index ? { ...r, status: "done", message: "Completed" } : r))
          );
          addLog(`Completed: ${row.name}`, "success");
        } else {
          throw new Error(result.message || "Fill failed");
        }
      } else {
        const err = await res.json();
        throw new Error(err.detail || "Request failed");
      }
    } catch (e: unknown) {
      const errorMessage = e instanceof Error ? e.message : "Unknown error";
      setSheetData((prev) =>
        prev.map((r, i) => (i === index ? { ...r, status: "error", message: errorMessage } : r))
      );
      addLog(`Error: ${errorMessage}`, "error");
    }
  };

  // Run full automation
  const runAutomation = async () => {
    if (sheetData.length === 0) {
      addLog("No data to process", "error");
      return;
    }

    // Check Chrome first
    await checkChromeConnection();
    if (!chromeConnected) {
      addLog("Please start Chrome with: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222", "error");
      return;
    }

    setAutomationRunning(true);
    setCurrentIndex(0);
    addLog("Starting automation...", "info");

    for (let i = 0; i < sheetData.length; i++) {
      if (sheetData[i].status === "done") continue;
      
      setCurrentIndex(i);
      await runSingleAutomation(i);
      
      // Small delay between items
      if (i < sheetData.length - 1) {
        await new Promise((r) => setTimeout(r, 2000));
      }
    }

    setAutomationRunning(false);
    addLog("Automation completed!", "success");
  };

  // Stop automation
  const stopAutomation = () => {
    setAutomationRunning(false);
    addLog("Automation stopped by user", "info");
  };

  const completedCount = sheetData.filter((r) => r.status === "done").length;
  const newCount = sheetData.filter((r) => r.priceChanged === "NEW" || r.priceChanged === "ADD").length;
  const priceChangedCount = sheetData.filter((r) => r.priceChanged === "YES").length;

  if (loading) {
    return (
      <div className="p-8 flex flex-col items-center justify-center gap-4">
        <p className="text-gray-500">Loading...</p>
        <p className="text-xs text-gray-400">Connecting to backend at {API_BASE_URL}</p>
        <button 
          onClick={() => setLoading(false)}
          className="text-sm text-blue-500 underline"
        >
          Skip loading
        </button>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-black">GEM Automation Data</h1>
        <p className="text-gray-500 mt-1">
          View products from Google Sheet - synced automatically when you scrape
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
        <div className="bg-white rounded-xl p-4 border border-[#e5e5e5]">
          <p className="text-sm text-gray-500">Total Products</p>
          <p className="text-2xl font-bold text-black">{sheetData.length}</p>
        </div>
        <div className="bg-white rounded-xl p-4 border border-[#e5e5e5]">
          <p className="text-sm text-gray-500">Done</p>
          <p className="text-2xl font-bold text-green-600">{completedCount}</p>
        </div>
        <div className="bg-white rounded-xl p-4 border border-[#e5e5e5]">
          <p className="text-sm text-gray-500">New Products</p>
          <p className="text-2xl font-bold text-blue-600">{newCount}</p>
        </div>
        <div className="bg-white rounded-xl p-4 border border-[#e5e5e5]">
          <p className="text-sm text-gray-500">Price Changed</p>
          <p className="text-2xl font-bold text-yellow-600">{priceChangedCount}</p>
        </div>
        <div className="bg-white rounded-xl p-4 border border-[#e5e5e5]">
          <p className="text-sm text-gray-500">Chrome Status</p>
          <p className={`text-lg font-bold ${
            formDetected ? "text-green-600" : 
            chromeConnected ? "text-yellow-600" : 
            "text-gray-400"
          }`}>
            {!chromeConnected ? "Not Connected" : 
             formDetected ? `${formType?.toUpperCase()} Form Ready` : 
             gemTabs.length > 0 ? "No Form Open" : 
             "No GEM Tabs"}
          </p>
          {chromeConnected && gemTabs.length > 0 && (
            <p className="text-xs text-gray-400 mt-1 truncate" title={gemTabs[0]?.title}>
              {gemTabs[0]?.title}
            </p>
          )}
        </div>
      </div>

      {!sheetsConnected ? (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6 text-center">
          <p className="text-yellow-700 mb-4">Google Sheets not connected</p>
          <a
            href="/integrations"
            className="inline-block px-6 py-2 bg-black text-white rounded-lg hover:bg-gray-800"
          >
            Connect Google Sheets
          </a>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Chrome & Form Status Panel */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-xl border border-[#e5e5e5] p-4">
              <div className="flex flex-wrap items-center gap-4">
                {/* Chrome Status */}
                <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
                  chromeConnected ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"
                }`}>
                  <div className={`w-3 h-3 rounded-full ${chromeConnected ? "bg-green-500 animate-pulse" : "bg-red-500"}`}></div>
                  <span className={`text-sm font-medium ${chromeConnected ? "text-green-700" : "text-red-700"}`}>
                    Chrome: {chromeConnected ? "Connected" : "Not Connected"}
                  </span>
                </div>

                {/* Form Status */}
                <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
                  formDetected 
                    ? "bg-green-50 border border-green-200" 
                    : chromeConnected 
                    ? "bg-yellow-50 border border-yellow-200"
                    : "bg-gray-50 border border-gray-200"
                }`}>
                  <div className={`w-3 h-3 rounded-full ${
                    formDetected ? "bg-green-500 animate-pulse" : chromeConnected ? "bg-yellow-500" : "bg-gray-400"
                  }`}></div>
                  <span className={`text-sm font-medium ${
                    formDetected ? "text-green-700" : chromeConnected ? "text-yellow-700" : "text-gray-500"
                  }`}>
                    Form: {formDetected ? `${formType?.toUpperCase()} Form Ready` : chromeConnected ? "Open GEM Form" : "Waiting..."}
                  </span>
                </div>

                {/* GEM Tabs */}
                {gemTabs.length > 0 && (
                  <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-50 border border-blue-200">
                    <span className="text-sm font-medium text-blue-700">
                      📑 {gemTabs.length} GEM Tab{gemTabs.length > 1 ? 's' : ''} Open
                    </span>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex gap-2 ml-auto">
                  <button
                    onClick={checkChromeConnection}
                    disabled={checkingChrome}
                    className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg disabled:opacity-50"
                  >
                    {checkingChrome ? "⏳ Checking..." : "🔄 Refresh Status"}
                  </button>
                  <button
                    onClick={launchDebugChrome}
                    className="px-3 py-1.5 text-sm bg-purple-600 text-white hover:bg-purple-700 rounded-lg"
                  >
                    🚀 Launch Chrome
                  </button>
                </div>
              </div>

              {/* Instructions */}
              {!chromeConnected && (
                <p className="mt-3 text-sm text-red-600">
                  👆 Click "Launch Chrome" to start Chrome with debug mode, then login to GEM portal
                </p>
              )}
              {chromeConnected && !formDetected && (
                <p className="mt-3 text-sm text-yellow-600">
                  👆 Chrome connected! Now open a product add/edit form on GEM portal, then click "Refresh Status"
                </p>
              )}
              {formDetected && (
                <p className="mt-3 text-sm text-green-600">
                  ✅ Ready! Click "Add Products" or "Update Products" below to start automation
                </p>
              )}
            </div>
          </div>

          {/* Sheet Selection & Data */}
          <div className="lg:col-span-2 space-y-6">
            {/* Sheet Selector */}
            <div className="bg-white rounded-xl border border-[#e5e5e5] p-6">
              <h3 className="text-lg font-semibold text-black mb-4">1. Select Data Source</h3>
              
              {/* Connected Sheets Dropdown */}
              {spreadsheets.length > 0 ? (
                <div className="flex gap-3 flex-wrap items-center">
                  <select
                    value={selectedSheet}
                    onChange={(e) => setSelectedSheet(e.target.value)}
                    className="flex-1 min-w-[200px] px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black"
                  >
                    {spreadsheets.map((sheet) => (
                      <option key={sheet.id} value={sheet.id}>
                        {sheet.name}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={checkChromeConnection}
                    disabled={checkingChrome}
                    className={`px-4 py-2 text-sm font-medium border rounded-lg disabled:opacity-50 ${
                      formDetected 
                        ? "border-green-500 text-green-600 bg-green-50" 
                        : chromeConnected
                        ? "border-yellow-500 text-yellow-600 bg-yellow-50"
                        : "border-gray-300 hover:bg-gray-50"
                    }`}
                  >
                    {checkingChrome ? "Checking..." : 
                     formDetected ? `✓ ${formType?.toUpperCase()} Form Ready` :
                     chromeConnected ? "⚠ Open Form" : 
                     "Check Chrome"}
                  </button>
                  <button
                    onClick={launchDebugChrome}
                    className="px-4 py-2 text-sm font-medium bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                  >
                    🚀 Launch Chrome (Debug)
                  </button>
                  <button
                    onClick={runAddProducts}
                    disabled={runningAdd || !formDetected}
                    title={!formDetected ? "Open the GEM product form first" : ""}
                    className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {runningAdd ? "Running..." : "Add Products (NEW)"}
                  </button>
                  <button
                    onClick={runUpdateProducts}
                    disabled={runningUpdate || !formDetected}
                    title={!formDetected ? "Open the GEM product form first" : ""}
                    className="px-4 py-2 text-sm font-medium bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                  >
                    {runningUpdate ? "Running..." : "Update Products (ACTIVE)"}
                  </button>
                  <button
                    onClick={stopRunningAutomation}
                    disabled={stoppingAutomation || (!runningAdd && !runningUpdate)}
                    className="px-4 py-2 text-sm font-medium bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                  >
                    {stoppingAutomation ? "Stopping..." : "🛑 Stop"}
                  </button>
                  {loadingData && (
                    <span className="text-sm text-gray-500">Loading...</span>
                  )}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No spreadsheets found in your Google account. Create one first.</p>
              )}
            </div>

            {/* Data Preview */}
            <div className="bg-white rounded-xl border border-[#e5e5e5]">
              <div className="p-4 border-b border-[#e5e5e5] flex items-center justify-between">
                <h3 className="text-lg font-semibold text-black">2. Products from Sheet</h3>
                <div className="flex gap-2 items-center">
                  <span className="text-xs text-gray-400">Auto-refresh: 30s</span>
                  <button
                    onClick={loadSheetData}
                    disabled={loadingData}
                    className="px-4 py-1.5 text-xs font-medium border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                  >
                    {loadingData ? "..." : "Refresh"}
                  </button>
                </div>
              </div>
              <div className="max-h-96 overflow-y-auto">
                {sheetData.length === 0 ? (
                  <div className="p-8 text-center text-gray-400">
                    {loadingData ? "Loading..." : "No data in sheet. Scrape products first."}
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Row</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Product ID</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Price</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Status</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600">Updated</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#e5e5e5]">
                      {sheetData.map((row, idx) => (
                        <tr
                          key={idx}
                          className={`hover:bg-gray-50 ${
                            row.priceChanged === "YES" ? "bg-yellow-50" : 
                            row.priceChanged === "NEW" ? "bg-green-50" : ""
                          }`}
                        >
                          <td className="px-3 py-2 text-gray-500 text-xs">{row.rowIndex}</td>
                          <td className="px-3 py-2">
                            <a 
                              href={row.url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="font-medium text-black hover:underline truncate block max-w-[200px]"
                              title={row.productId}
                            >
                              {row.productId}
                            </a>
                          </td>
                          <td className="px-3 py-2">
                            <span className="text-gray-900">₹{row.price}</span>
                            {row.prevPrice && row.priceChanged === "YES" && (
                              <span className="ml-1 text-xs text-gray-400 line-through">₹{row.prevPrice}</span>
                            )}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                row.priceChanged === "NEW" || row.priceChanged === "ADD"
                                  ? row.status === "done" 
                                    ? "bg-green-100 text-green-700"
                                    : "bg-blue-100 text-blue-700"
                                  : row.priceChanged === "YES"
                                  ? "bg-yellow-100 text-yellow-700"
                                  : "bg-gray-100 text-gray-600"
                              }`}
                            >
                              {/* Always show Column C value, add ✓ if processed */}
                              {row.priceChanged === "NEW" ? (row.status === "done" ? "NEW ✓" : "NEW") : 
                               row.priceChanged === "ADD" ? (row.status === "done" ? "ADD ✓" : "ADD") :
                               row.priceChanged === "YES" ? "PRICE CHANGED" : 
                               row.priceChanged || "Pending"}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-xs text-gray-400">
                            {row.lastUpdated || "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

          {/* Logs */}
          <div className="bg-white rounded-xl border border-[#e5e5e5]">
            <div className="p-4 border-b border-[#e5e5e5] flex items-center justify-between">
              <h3 className="text-lg font-semibold text-black">Activity Log</h3>
              <button
                onClick={() => setLogs([])}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                Clear
              </button>
            </div>
            <div className="p-4 max-h-[500px] overflow-y-auto space-y-2">
              {logs.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">No activity yet</p>
              ) : (
                logs.map((log, idx) => (
                  <div
                    key={idx}
                    className={`text-xs p-2 rounded ${
                      log.type === "success"
                        ? "bg-green-50 text-green-700"
                        : log.type === "error"
                        ? "bg-red-50 text-red-700"
                        : log.type === "otp"
                        ? "bg-yellow-50 text-yellow-700"
                        : "bg-gray-50 text-gray-600"
                    }`}
                  >
                    <span className="font-mono text-gray-400">{log.time}</span> {log.message}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Info */}
      <div className="mt-6 bg-gray-50 rounded-xl border border-[#e5e5e5] p-4">
        <h4 className="font-medium text-black mb-2">How it works</h4>
        <ol className="text-sm text-gray-600 space-y-1 list-decimal list-inside">
          <li>Scrape products from Dashboard → Data auto-saved to Google Sheet</li>
          <li>This page shows sheet data with auto-refresh every 30 seconds</li>
          <li>New products show in blue, price changes in yellow</li>
          <li>Client uses <code className="bg-gray-200 px-1 rounded">gem_add.py</code> Selenium script to fill GEM forms</li>
          <li>OTP is auto-fetched from Gmail when needed</li>
        </ol>
      </div>

      {/* Chrome Help Modal */}
      {showChromeHelp && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-lg w-full mx-4 shadow-2xl">
            <h3 className="text-lg font-bold text-black mb-4">🚀 Launch Chrome with Debug Mode</h3>
            
            <div className="mb-4">
              <p className="text-sm text-gray-600 mb-3">
                Chrome must be started with remote debugging enabled. Follow these steps:
              </p>
              
              <ol className="text-sm text-gray-700 space-y-2 list-decimal list-inside mb-4">
                <li><strong>Close ALL Chrome windows</strong> (completely exit Chrome)</li>
                <li>Open <strong>Terminal</strong> (Mac) or <strong>Command Prompt</strong> (Windows)</li>
                <li>Copy and paste this command:</li>
              </ol>
              
              <div className="bg-gray-900 text-green-400 p-3 rounded-lg font-mono text-xs overflow-x-auto whitespace-pre-wrap break-all">
                {chromeCommand || '/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222'}
              </div>
              
              <button
                onClick={() => {
                  navigator.clipboard.writeText(chromeCommand || '/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222');
                  addLog("Command copied to clipboard!", "success");
                }}
                className="mt-2 text-sm text-blue-600 hover:underline"
              >
                📋 Copy Command
              </button>
            </div>
            
            <ol className="text-sm text-gray-700 space-y-2 list-decimal list-inside mb-4" start={4}>
              <li>A new Chrome window will open</li>
              <li><strong>Login to GEM portal</strong> in that window</li>
              <li>Come back here and click <strong>"Check Chrome"</strong></li>
            </ol>
            
            <div className="flex gap-3">
              <button
                onClick={() => setShowChromeHelp(false)}
                className="flex-1 px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800"
              >
                Got it!
              </button>
              <button
                onClick={() => {
                  setShowChromeHelp(false);
                  checkChromeConnection();
                }}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Check Connection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
