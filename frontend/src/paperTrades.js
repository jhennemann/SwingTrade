import { supabase } from "./supabase.js";

export async function getOpenTrades() {
  const { data } = await supabase
    .from("paper_trades")
    .select("*")
    .eq("status", "open")
    .order("relative_strength", { ascending: false });
  return data ?? [];
}

export async function getClosedTrades() {
  const { data } = await supabase
    .from("paper_trades")
    .select("*")
    .eq("status", "closed")
    .order("exit_date", { ascending: false });
  return data ?? [];
}

export async function getEquityCurve() {
  const { data } = await supabase
    .from("paper_equity_curve")
    .select("*")
    .order("date", { ascending: true });
  return data ?? [];
}

export async function getAccountSummary() {
  const { data } = await supabase.from("paper_account_summary").select("*");
  return data ?? [];
}

export async function getTradeStats() {
  const { data } = await supabase.from("paper_trade_stats").select("*");
  return data ?? [];
}
