"use client";
import { useEffect, useState } from "react";
type Report = { paid_tax_toman: number; refunded_tax_toman: number; paid_orders: number; order_total_toman: number; captured_toman: number; refunded_toman: number; net_received_toman: number; open_returns: number; deliveries: Record<string, number> };
export function SalesReport() {
  const [report, setReport] = useState<Report | null>(null); const [error, setError] = useState("");
  useEffect(() => { fetch("/api/v1/operations/reports/sales/").then(async (response) => { if (!response.ok) throw new Error(); setReport(await response.json()); }).catch(() => setError("گزارش دریافت نشد.")); }, []);
  return <section className="admin-card"><h1>گزارش فروش و عملیات</h1>{error && <p role="alert">{error}</p>}{report && <><p>سفارش‌های پرداخت‌شده: {report.paid_orders}</p><p>جمع سفارش‌ها: {report.order_total_toman.toLocaleString("fa-IR")} تومان</p><p>مالیات سفارش‌های پرداخت‌شده: {report.paid_tax_toman.toLocaleString("fa-IR")} تومان · مالیات بازپرداخت‌شده در پرونده‌ها: {report.refunded_tax_toman.toLocaleString("fa-IR")} تومان</p><p>دریافت ثبت‌شده: {report.captured_toman.toLocaleString("fa-IR")} تومان</p><p>استرداد ثبت‌شده: {report.refunded_toman.toLocaleString("fa-IR")} تومان</p><p>خالص دریافت: {report.net_received_toman.toLocaleString("fa-IR")} تومان</p><p>مرجوعی باز: {report.open_returns}</p><ul>{Object.entries(report.deliveries).map(([key, value]) => <li key={key}>{key}: {value}</li>)}</ul><p>دریافت‌های نیازمند بررسی هم در دریافت ثبت‌شده لحاظ می‌شوند. مبالغ حالت آزمایشی انتقال پول واقعی نیستند.</p></>}</section>;
}
