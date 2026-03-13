"use client";

import { useState, useEffect } from "react";
import { getSheetsStatus, listSpreadsheets, upsertProducts, getStats, Stats } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STORAGE_KEY = "gem_scrape_categories";
const PRODUCTS_KEY = "gem_scraped_products";

interface Category {
  name: string;
  slug: string;
  product_count: number;
}

interface ScrapeCategory {
  id: number;
  name: string;
  slug: string;
  productCount: number;
  status: "pending" | "scraping" | "completed" | "error";
  scrapedProducts: number;
  lastScraped: string | null;
}

interface Product {
  id: string;
  title: string;
  brand: string;
  list_price: number;
  final_price: number;
  discount_percent: number;
  seller: { name: string };
  url: string;
}

interface ScrapedData {
  [slug: string]: {
    name: string;
    products: Product[];
    scrapedAt: string;
  };
}

interface Spreadsheet {
  id: string;
  name: string;
}

export default function DashboardPage() {
  const [searchKeyword, setSearchKeyword] = useState("");
  const [searchResults, setSearchResults] = useState<Category[]>([]);
  const [searching, setSearching] = useState(false);
  const [categories, setCategories] = useState<ScrapeCategory[]>([]);
  const [scrapeStatus, setScrapeStatus] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [scrapedData, setScrapedData] = useState<ScrapedData>({});
  const [viewingSlug, setViewingSlug] = useState<string | null>(null);
  
  // Sheet integration state
  const [sheetsConnected, setSheetsConnected] = useState(false);
  const [spreadsheets, setSpreadsheets] = useState<Spreadsheet[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<string>("");
  const [manualSheetId, setManualSheetId] = useState<string>("");
  const [savingToSheet, setSavingToSheet] = useState<string | null>(null);
  const [saveResult, setSaveResult] = useState<{ success: boolean; message: string } | null>(null);
  
  // Realtime pricing option (slower but accurate) - default ON
  const [realtimePrices, setRealtimePrices] = useState(true);
  
  // Real stats from database
  const [dbStats, setDbStats] = useState<Stats | null>(null);

  // Load categories from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // Reset any "scraping" status to "pending" on reload
        const restored = parsed.map((c: ScrapeCategory) => ({
          ...c,
          status: c.status === "scraping" ? "pending" : c.status,
        }));
        setCategories(restored);
      } catch (e) {
        console.error("Failed to load saved categories:", e);
      }
    }
    // Load scraped products
    const savedProducts = localStorage.getItem(PRODUCTS_KEY);
    if (savedProducts) {
      try {
        setScrapedData(JSON.parse(savedProducts));
      } catch (e) {
        console.error("Failed to load saved products:", e);
      }
    }
    setIsLoaded(true);
  }, []);

  // Save categories to localStorage when they change (after initial load)
  useEffect(() => {
    if (!isLoaded) return;
    if (categories.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(categories));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [categories, isLoaded]);

  // Save scraped data to localStorage
  useEffect(() => {
    if (!isLoaded) return;
    if (Object.keys(scrapedData).length > 0) {
      localStorage.setItem(PRODUCTS_KEY, JSON.stringify(scrapedData));
    }
  }, [scrapedData, isLoaded]);

  // Load sheets status
  useEffect(() => {
    const loadSheetsStatus = async () => {
      try {
        const status = await getSheetsStatus();
        setSheetsConnected(status.connected);
        if (status.connected) {
          const sheets = await listSpreadsheets();
          setSpreadsheets(sheets || []);
          if (sheets && sheets.length > 0) {
            setSelectedSheet(sheets[0].id);
          }
        }
      } catch (e) {
        console.error("Failed to load sheets status:", e);
      }
    };
    loadSheetsStatus();
  }, []);

  // Load stats from database
  useEffect(() => {
    const loadStats = async () => {
      try {
        const stats = await getStats();
        setDbStats(stats);
      } catch (e) {
        console.error("Failed to load stats:", e);
      }
    };
    loadStats();
    // Refresh stats every 30 seconds
    const interval = setInterval(loadStats, 30000);
    return () => clearInterval(interval);
  }, []);

  // Search categories by keyword
  const handleSearch = async () => {
    if (!searchKeyword.trim()) return;
    setSearching(true);
    setSearchResults([]);
    try {
      const res = await fetch(`${API_BASE_URL}/api/categories?q=${encodeURIComponent(searchKeyword)}`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.categories || []);
      } else {
        alert("Search failed. Make sure backend is running on port 8000.");
      }
    } catch (error) {
      console.error("Search failed:", error);
      alert("Cannot connect to backend. Start it with: uvicorn app.main:app --reload");
    } finally {
      setSearching(false);
    }
  };

  // Add category to scrape list
  const handleAddCategory = (cat: Category) => {
    if (categories.some((c) => c.slug === cat.slug)) {
      alert("Category already added");
      return;
    }
    const newCat: ScrapeCategory = {
      id: Date.now(),
      name: cat.name,
      slug: cat.slug,
      productCount: cat.product_count,
      status: "pending",
      scrapedProducts: 0,
      lastScraped: null,
    };
    setCategories([...categories, newCat]);
    // Remove from search results
    setSearchResults(searchResults.filter((c) => c.slug !== cat.slug));
  };

  // Remove category from list
  const handleRemoveCategory = (id: number) => {
    setCategories(categories.filter((c) => c.id !== id));
  };

  // Scrape single category
  const handleScrapeCategory = async (id: number) => {
    const cat = categories.find((c) => c.id === id);
    if (!cat) return;

    setCategories((prev) =>
      prev.map((c) => (c.id === id ? { ...c, status: "scraping" } : c))
    );

    try {
      // Use realtime=true for accurate live prices (slower)
      const realtimeParam = realtimePrices ? "&realtime=true" : "";
      const res = await fetch(`${API_BASE_URL}/api/products/${encodeURIComponent(cat.slug)}/all?${realtimeParam}`);
      if (res.ok) {
        const data = await res.json();
        const products = data.products || [];
        
        // Store scraped products locally
        setScrapedData((prev) => ({
          ...prev,
          [cat.slug]: {
            name: cat.name,
            products: products,
            scrapedAt: new Date().toISOString(),
          },
        }));
        
        // Auto-save to selected sheet if one is chosen
        if (selectedSheet && products.length > 0) {
          try {
            // Use upsert: updates existing products, inserts new ones, tracks price changes
            const result = await upsertProducts(selectedSheet, products);
            
            let message = ``;
            if (result.inserted > 0) message += `${result.inserted} new`;
            if (result.updated > 0) message += `${message ? ', ' : ''}${result.updated} updated`;
            if (result.price_changes > 0) message += ` (${result.price_changes} price changes)`;
            
            setSaveResult({ success: true, message: message || 'Sheet updated' });
            setTimeout(() => setSaveResult(null), 5000);
            
            // Refresh stats after successful upsert
            try {
              const stats = await getStats();
              setDbStats(stats);
            } catch (e) {
              console.error("Failed to refresh stats:", e);
            }
          } catch (sheetError) {
            console.error("Failed to save to sheet:", sheetError);
            setSaveResult({ success: false, message: "Failed to save to sheet" });
            setTimeout(() => setSaveResult(null), 3000);
          }
        }
        
        setCategories((prev) =>
          prev.map((c) =>
            c.id === id
              ? {
                  ...c,
                  status: "completed",
                  scrapedProducts: data.count || 0,
                  lastScraped: new Date().toLocaleTimeString(),
                }
              : c
          )
        );
      } else {
        throw new Error("Scrape failed");
      }
    } catch {
      setCategories((prev) =>
        prev.map((c) => (c.id === id ? { ...c, status: "error" } : c))
      );
    }
  };

  // Scrape all categories
  const handleScrapeAll = async () => {
    if (categories.length === 0) return;
    setScrapeStatus("Starting automation...");
    
    for (let i = 0; i < categories.length; i++) {
      const cat = categories[i];
      if (cat.status === "completed") continue;
      
      setScrapeStatus(`Scraping ${i + 1}/${categories.length}: ${cat.name}`);
      await handleScrapeCategory(cat.id);
      // Small delay between requests
      await new Promise((r) => setTimeout(r, 1000));
    }
    
    setScrapeStatus(null);
  };

  // Download JSON
  const downloadJSON = (slug: string) => {
    const data = scrapedData[slug];
    if (!data) return;
    const blob = new Blob([JSON.stringify(data.products, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${slug}-products.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Download CSV
  const downloadCSV = (slug: string) => {
    const data = scrapedData[slug];
    if (!data || data.products.length === 0) return;
    
    // Get all unique keys from products
    const keys = Array.from(new Set(data.products.flatMap((p) => Object.keys(p))));
    const headers = keys.join(',');
    const rows = data.products.map((p) => 
      keys.map((k) => {
        const val = p[k as keyof Product];
        if (val === null || val === undefined) return '';
        const str = String(val);
        // Escape quotes and wrap in quotes if contains comma
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(',')
    );
    
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${slug}-products.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Save to Google Sheet
  const saveToSheet = async (slug: string) => {
    const sheetId = selectedSheet || manualSheetId;
    if (!sheetId) {
      alert("Please enter a Sheet ID or select a sheet");
      return;
    }
    const data = scrapedData[slug];
    if (!data || data.products.length === 0) {
      alert("No data to save");
      return;
    }

    setSavingToSheet(slug);
    setSaveResult(null);
    
    try {
      // Prepare rows - headers + data
      const headers = ["Product Name", "Price", "Unit", "Seller", "Product ID", "Category", "URL"];
      const rows = data.products.map((p: Product) => [
        p.title || "",
        String(p.final_price || p.list_price || ""),
        "",
        typeof p.seller === "object" ? p.seller?.name || "" : String(p.seller || ""),
        p.id || "",
        data.name || slug,
        p.url || ""
      ]);

      const res = await fetch(`${API_BASE_URL}/api/sheets/${sheetId}/write`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          range: "Sheet1!A1",
          values: [headers, ...rows]
        })
      });

      if (res.ok) {
        setSaveResult({ success: true, message: `Saved ${data.products.length} products to sheet!` });
      } else {
        const err = await res.json();
        setSaveResult({ success: false, message: err.detail || "Failed to save" });
      }
    } catch (e) {
      setSaveResult({ success: false, message: "Failed to connect to server" });
    } finally {
      setSavingToSheet(null);
    }
  };

  const totalProducts = categories.reduce((sum, c) => sum + c.scrapedProducts, 0);
  const completedCount = categories.filter((c) => c.status === "completed").length;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-black">GEM Scrape Automation</h1>
        <p className="text-gray-500 mt-1">Search categories, add to list, and run automated scraping</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
        <div className="bg-white rounded-xl p-4 border border-[#e5e5e5]">
          <p className="text-sm text-gray-500">Session Categories</p>
          <p className="text-2xl font-bold text-black">{categories.length}</p>
        </div>
        <div className="bg-white rounded-xl p-4 border border-[#e5e5e5]">
          <p className="text-sm text-gray-500">Completed</p>
          <p className="text-2xl font-bold text-black">{completedCount}/{categories.length}</p>
        </div>
        <div className="bg-white rounded-xl p-4 border border-[#e5e5e5]">
          <p className="text-sm text-gray-500">Today Scraped</p>
          <p className="text-2xl font-bold text-blue-600">{dbStats?.today.products_scraped.toLocaleString() || 0}</p>
        </div>
        <div className="bg-white rounded-xl p-4 border border-[#e5e5e5]">
          <p className="text-sm text-gray-500">Total Products</p>
          <p className="text-2xl font-bold text-black">{dbStats?.overall.total_products.toLocaleString() || 0}</p>
        </div>
        <div className="bg-white rounded-xl p-4 border border-[#e5e5e5]">
          <p className="text-sm text-gray-500">Price Changes</p>
          <p className="text-2xl font-bold text-orange-500">{dbStats?.overall.total_price_changes.toLocaleString() || 0}</p>
        </div>
        <div className="bg-white rounded-xl p-4 border border-[#e5e5e5]">
          <p className="text-sm text-gray-500">New Products</p>
          <p className="text-2xl font-bold text-green-600">{dbStats?.overall.total_new_products.toLocaleString() || 0}</p>
        </div>
      </div>

      {/* Scrape Status Banner */}
      {scrapeStatus && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-3">
          <svg className="w-5 h-5 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-sm font-medium text-blue-700">{scrapeStatus}</p>
        </div>
      )}

      {/* Save Result Toast */}
      {saveResult && (
        <div className={`mb-6 p-4 rounded-lg flex items-center gap-3 ${saveResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
          <svg className={`w-5 h-5 ${saveResult.success ? 'text-green-600' : 'text-red-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {saveResult.success ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            )}
          </svg>
          <p className={`text-sm font-medium ${saveResult.success ? 'text-green-700' : 'text-red-700'}`}>{saveResult.message}</p>
        </div>
      )}

      {/* Sheet Selector */}
      {sheetsConnected && (
        <div className="mb-6 p-4 bg-white border border-[#e5e5e5] rounded-xl">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
              <span className="text-sm font-medium text-black">Auto-save to:</span>
            </div>
            <select
              value={selectedSheet}
              onChange={(e) => setSelectedSheet(e.target.value)}
              className="flex-1 max-w-md px-3 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black"
            >
              <option value="">Select a sheet (optional)</option>
              {spreadsheets.map((sheet) => (
                <option key={sheet.id} value={sheet.id}>
                  {sheet.name}
                </option>
              ))}
            </select>
            {selectedSheet && (
              <span className="text-xs text-green-600 flex items-center gap-1">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Scraped data will be saved automatically
              </span>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Search Section */}
        <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm">
          <div className="p-6 border-b border-[#e5e5e5]">
            <h3 className="text-lg font-semibold text-black">1. Search Categories</h3>
            <p className="text-sm text-gray-500 mt-1">Enter keyword to find relevant GEM categories</p>
          </div>
          <div className="p-6">
            <div className="flex gap-3 mb-4">
              <input
                type="text"
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="e.g., safety shoes, gloves, laptop..."
                className="flex-1 px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
              <button
                onClick={handleSearch}
                disabled={searching || !searchKeyword.trim()}
                className="px-6 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 disabled:opacity-50"
              >
                {searching ? "Searching..." : "Search"}
              </button>
            </div>

            {/* Search Results */}
            {searchResults.length > 0 && (
              <div className="border border-[#e5e5e5] rounded-lg overflow-hidden">
                <div className="bg-gray-50 px-4 py-2 text-xs font-medium text-gray-500 uppercase">
                  Found {searchResults.length} Categories
                </div>
                <div className="divide-y divide-[#e5e5e5] max-h-80 overflow-y-auto">
                  {searchResults.map((cat, idx) => (
                    <div key={idx} className="px-4 py-3 flex items-center justify-between hover:bg-gray-50">
                      <div>
                        <p className="text-sm font-medium text-black">{cat.name}</p>
                        <p className="text-xs text-gray-500">{cat.product_count.toLocaleString()} products</p>
                      </div>
                      <button
                        onClick={() => handleAddCategory(cat)}
                        className="px-3 py-1.5 text-xs font-medium text-white bg-black rounded hover:bg-gray-800"
                      >
                        + Add
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {searchResults.length === 0 && searchKeyword && !searching && (
              <p className="text-sm text-gray-400 text-center py-8">
                No results yet. Click Search to find categories.
              </p>
            )}
          </div>
        </div>

        {/* Categories to Scrape */}
        <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm">
          <div className="p-6 border-b border-[#e5e5e5] flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-black">2. Categories to Scrape</h3>
              <p className="text-sm text-gray-500 mt-1">Added categories for automation</p>
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer" title="Fetch real prices from product pages (slower but accurate)">
                <input
                  type="checkbox"
                  checked={realtimePrices}
                  onChange={(e) => setRealtimePrices(e.target.checked)}
                  className="w-4 h-4 accent-black"
                />
                <span className="text-sm text-gray-600">Real-time Prices</span>
              </label>
              <button
                onClick={handleScrapeAll}
                disabled={categories.length === 0 || !!scrapeStatus}
                className="px-4 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 disabled:opacity-50"
              >
                Run Automation
              </button>
            </div>
          </div>
          <div className="p-6">
            {categories.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">
                No categories added. Search and add categories from the left panel.
              </p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {categories.map((cat) => (
                  <div
                    key={cat.id}
                    className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-black truncate">{cat.name}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span
                          className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                            cat.status === "completed"
                              ? "bg-green-100 text-green-700"
                              : cat.status === "scraping"
                              ? "bg-blue-100 text-blue-700"
                              : cat.status === "error"
                              ? "bg-red-100 text-red-700"
                              : "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {cat.status}
                        </span>
                        <span className="text-xs text-gray-500">
                          {cat.scrapedProducts > 0
                            ? `${cat.scrapedProducts} scraped`
                            : `${cat.productCount.toLocaleString()} available`}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      {cat.status === "completed" && scrapedData[cat.slug] && (
                        <button
                          onClick={() => setViewingSlug(cat.slug)}
                          className="px-3 py-1.5 text-xs font-medium bg-green-600 text-white rounded hover:bg-green-700"
                        >
                          View ({scrapedData[cat.slug].products.length})
                        </button>
                      )}
                      <button
                        onClick={() => handleScrapeCategory(cat.id)}
                        disabled={cat.status === "scraping" || !!scrapeStatus}
                        className="px-3 py-1.5 text-xs font-medium border border-black rounded hover:bg-black hover:text-white disabled:opacity-50"
                      >
                        Scrape
                      </button>
                      <button
                        onClick={() => handleRemoveCategory(cat.id)}
                        disabled={cat.status === "scraping"}
                        className="p-1.5 text-gray-400 hover:text-red-500"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Product Viewer Modal */}
      {viewingSlug && scrapedData[viewingSlug] && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
            <div className="p-4 border-b border-[#e5e5e5] flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-black">{scrapedData[viewingSlug].name}</h3>
                <p className="text-sm text-gray-500">
                  {scrapedData[viewingSlug].products.length} products • Scraped {new Date(scrapedData[viewingSlug].scrapedAt).toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => downloadJSON(viewingSlug)}
                  className="px-3 py-1.5 text-sm font-medium bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Download JSON
                </button>
                <button
                  onClick={() => downloadCSV(viewingSlug)}
                  className="px-3 py-1.5 text-sm font-medium bg-green-600 text-white rounded hover:bg-green-700"
                >
                  Download CSV
                </button>
                <button
                  onClick={() => setViewingSlug(null)}
                  className="p-2 text-gray-400 hover:text-black"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            
            {/* Save to Sheet Section */}
            {sheetsConnected && (
              <div className="p-4 border-b border-[#e5e5e5] bg-gray-50">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-sm font-medium text-gray-700">Save to Google Sheet:</span>
                  {spreadsheets.length > 0 ? (
                    <select
                      value={selectedSheet}
                      onChange={(e) => setSelectedSheet(e.target.value)}
                      className="flex-1 max-w-xs px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-black"
                    >
                      {spreadsheets.map((sheet) => (
                        <option key={sheet.id} value={sheet.id}>{sheet.name}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={manualSheetId}
                      onChange={(e) => setManualSheetId(e.target.value)}
                      placeholder="Paste Sheet ID from URL"
                      className="flex-1 max-w-xs px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-black"
                    />
                  )}
                  <button
                    onClick={() => saveToSheet(viewingSlug)}
                    disabled={savingToSheet === viewingSlug || (!selectedSheet && !manualSheetId)}
                    className="px-4 py-1.5 text-sm font-medium bg-black text-white rounded hover:bg-gray-800 disabled:opacity-50"
                  >
                    {savingToSheet === viewingSlug ? "Saving..." : "Save to Sheet"}
                  </button>
                </div>
                {spreadsheets.length === 0 && (
                  <p className="mt-1 text-xs text-gray-500">
                    Get ID from: docs.google.com/spreadsheets/d/<span className="font-mono bg-gray-200 px-1">SHEET_ID</span>/edit
                  </p>
                )}
                {saveResult && (
                  <p className={`mt-2 text-sm ${saveResult.success ? "text-green-600" : "text-red-600"}`}>
                    {saveResult.message}
                  </p>
                )}
              </div>
            )}
            {!sheetsConnected && (
              <div className="p-4 border-b border-[#e5e5e5] bg-yellow-50">
                <p className="text-sm text-yellow-700">
                  <a href="/integrations" className="underline font-medium">Connect Google Sheets</a> to save scraped data directly to a spreadsheet.
                </p>
              </div>
            )}
            
            <div className="flex-1 overflow-auto p-4">
              <pre className="text-xs bg-gray-50 p-4 rounded-lg overflow-auto whitespace-pre-wrap">
                {JSON.stringify(scrapedData[viewingSlug].products, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
