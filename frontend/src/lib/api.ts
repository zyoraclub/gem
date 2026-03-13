const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Helper to get auth headers
function getAuthHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("gem_token");
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

export interface Stats {
  today: {
    products_scraped: number;
    categories_scraped: number;
    price_changes: number;
    new_products: number;
    products_updated: number;
  };
  weekly: {
    products_scraped: number;
    categories_scraped: number;
    price_changes: number;
  };
  overall: {
    total_products: number;
    total_categories: number;
    total_price_changes: number;
    total_new_products: number;
  };
}

export interface GmailStatus {
  connected: boolean;
  email?: string;
}

export interface SheetsStatus {
  connected: boolean;
  email?: string;
}

export interface ConnectedSheet {
  id: number;
  sheet_id: string;
  name: string;
  spreadsheet_name?: string;
  sheet_name?: string;
  url?: string;
  last_synced_at?: string;
  connected_at?: string;
}

export interface GemAccount {
  id: number;
  email: string;
  status: string;
  daily_upload_count: number;
  daily_limit: number;
  last_used: string | null;
}

// Dashboard Stats
export async function getStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE_URL}/api/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

// Gmail Integration
export async function getGmailStatus(): Promise<GmailStatus> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/gmail/status`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error("Failed to fetch Gmail status");
    return res.json();
  } catch {
    return { connected: false };
  }
}

export async function connectGmail(): Promise<{ auth_url: string }> {
  const res = await fetch(`${API_BASE_URL}/api/gmail/connect`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to initiate Gmail connection");
  return res.json();
}

export async function disconnectGmail(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/gmail/disconnect`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to disconnect Gmail");
}

// Gmail IMAP Settings
export interface GmailImapSettings {
  email: string;
  has_password: boolean;
  imap_server: string;
  imap_port: number;
  configured: boolean;
}

export async function getGmailImapSettings(): Promise<GmailImapSettings> {
  const res = await fetch(`${API_BASE_URL}/api/gmail/imap-settings`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch Gmail IMAP settings");
  return res.json();
}

export async function saveGmailImapSettings(settings: {
  email: string;
  app_password: string;
  imap_server?: string;
  imap_port?: number;
}): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE_URL}/api/gmail/imap-settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({
      email: settings.email,
      app_password: settings.app_password,
      imap_server: settings.imap_server || "imap.gmail.com",
      imap_port: settings.imap_port || 993,
    }),
  });
  if (!res.ok) throw new Error("Failed to save Gmail IMAP settings");
  return res.json();
}

export async function testGmailImap(): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE_URL}/api/gmail/test-imap`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to test Gmail IMAP");
  return res.json();
}

// Google Sheets Integration
export async function getSheetsStatus(): Promise<SheetsStatus> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/sheets/status`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error("Failed to fetch Sheets status");
    return res.json();
  } catch {
    return { connected: false };
  }
}

export async function connectSheets(): Promise<{ auth_url: string }> {
  const res = await fetch(`${API_BASE_URL}/api/sheets/connect`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to initiate Sheets connection");
  return res.json();
}

export async function disconnectSheets(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/sheets/disconnect`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to disconnect Sheets");
}

export async function getConnectedSheets(): Promise<ConnectedSheet[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/sheets/connected`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error("Failed to fetch connected sheets");
    const data = await res.json();
    return data.sheets || [];
  } catch {
    return [];
  }
}

export async function listSpreadsheets(): Promise<{ id: string; name: string }[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/sheets/list`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error("Failed to list spreadsheets");
    const data = await res.json();
    return data.spreadsheets || [];
  } catch {
    return [];
  }
}

export async function writeToSheet(
  sheetId: string,
  range: string,
  values: unknown[][]
): Promise<{ updatedCells: number }> {
  const res = await fetch(
    `${API_BASE_URL}/api/sheets/${sheetId}/write?range=${encodeURIComponent(range)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify(values),
    }
  );
  if (!res.ok) throw new Error("Failed to write to sheet");
  return res.json();
}

export async function appendToSheet(
  sheetId: string,
  values: unknown[][]
): Promise<{ updated_cells: number; updated_rows: number }> {
  const res = await fetch(
    `${API_BASE_URL}/api/sheets/${sheetId}/append?range=A1`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify(values),
    }
  );
  if (!res.ok) throw new Error("Failed to append to sheet");
  return res.json();
}

export interface UpsertResult {
  updated: number;
  inserted: number;
  price_changes: number;
  price_change_details: Array<{
    id: string;
    old_price: string;
    new_price: string;
  }>;
}

export async function upsertProducts(
  sheetId: string,
  products: unknown[]
): Promise<UpsertResult> {
  const res = await fetch(
    `${API_BASE_URL}/api/sheets/${sheetId}/upsert`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify(products),
    }
  );
  if (!res.ok) throw new Error("Failed to upsert products");
  return res.json();
}

// GEM Accounts
export async function getGemAccounts(): Promise<GemAccount[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/accounts`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error("Failed to fetch accounts");
    return res.json();
  } catch {
    return [];
  }
}

export async function addGemAccount(email: string, password: string): Promise<GemAccount> {
  const res = await fetch(`${API_BASE_URL}/api/accounts`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Failed to add account");
  return res.json();
}

export async function deleteGemAccount(id: number): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/accounts/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to delete account");
}
