/* Local-only prototype API. This file is loaded by the ui-redesign branch only. */
(function () {
  const state = JSON.parse(localStorage.getItem("brickfactory-mock-state") || "null") || {
    role: "admin",
    username: "Demo Admin",
    bricksPerMix: 182,
    outletStock: 18420,
    stock: { Flyash: 4000, Sand: 2000, Chemical: 260, Cement: 480 },
    defaultPrice: 7.5,
    sales: [
      { sale_id: 101, sale_date: "2026-09-06", sale_timestamp: "09:15:00", customer_name: "Anand Builders", customer_mobile: "9876543210", bricks_purchased: 1200, total_amount: 9000, amount_paid: 9000, balance_due: 0 },
      { sale_id: 100, sale_date: "2026-09-05", sale_timestamp: "16:40:00", customer_name: "Green Valley Homes", customer_mobile: "9847001122", bricks_purchased: 800, total_amount: 6000, amount_paid: 3500, balance_due: 2500 },
    ],
  };

  const save = () => localStorage.setItem("brickfactory-mock-state", JSON.stringify(state));
  const json = (value) => Promise.resolve(value);
  const materials = () => Object.fromEntries(Object.entries(state.stock).map(([name, quantity]) => [name, { quantity, unit: name === "Chemical" ? "L" : name === "Cement" ? "packets" : "kg" }]));
  const sales = () => state.sales.map((sale) => ({ ...sale, balance_due: sale.balance_due ?? sale.total_amount - sale.amount_paid }));
  const dashboard = {
    date: "2026-09-06", bricks_produced: 3640, bricks_sold: 2000, pending_customer_dues: 2500,
    production: { mixes: 20, bricks: 3640, labourers: 8, misc_expense: 850 },
    sales: { count: 2, total: 15000, paid: 12500, pending: 2500 },
  };

  function response(path, method, body) {
    if (path === "/login") {
      const username = body?.username || "demo";
      return { access_token: "mock-token", username, role: username.toLowerCase().includes("manager") ? "manager" : "admin" };
    }
    if (path === "/stock" || path === "/manager/stock") return materials();
    if (path === "/manager/bricks-per-mix") return { bricks_per_mix: state.bricksPerMix };
    if (path === "/manager/stock/refill") {
      state.stock[body.material] = (state.stock[body.material] || 0) + Number(body.amount || 0); save();
      return { material: body.material, added: Number(body.amount), new_total: state.stock[body.material], unit: materials()[body.material].unit };
    }
    if (path === "/manager/production/today") return { exists: true, timestamp: "08:05:00", mixes: 20, bricks_produced: 3640, labourers: 8, misc_amount: 850, misc_note: "Transport", is_corrected: "no" };
    if (path === "/manager/production/preview") {
      const mixes = body.mixes ?? Math.round(Number(body.bricks_produced) / state.bricksPerMix);
      const bricks = body.bricks_produced ?? Math.round(Number(body.mixes) * state.bricksPerMix);
      return { mixes, bricks_produced: bricks, calculated_field: body.mixes == null ? "mixes" : body.bricks_produced == null ? "bricks" : "none", avg_bricks_per_mix: Math.round(bricks / mixes) };
    }
    if (path === "/manager/sales" || path === "/manager/sales/today" || path === "/brick-sales") return sales();
    if (path === "/manager/sales/outlet-stock" || path === "/brick-sales/outlet-stock") return { total_bricks: state.outletStock };
    if (path.includes("/manager/sales/customers/") && path.endsWith("/history")) return { summary: "Demo customer history", orders: sales() };
    if (path.includes("/manager/sales/customers/search")) return [{ customer_name: "Anand Builders", customer_mobile: "9876543210", total_bricks: 1200, total_billed: 9000, pending_dues: 0 }];
    if (path === "/manager/sales/default-price" || path === "/default-brick-price") return { default_cost_per_brick: state.defaultPrice };
    if (path === "/manager/sales/stock-adjustments") return { adjustments: [] };
    if (path === "/rates") return { Flyash: { current_rate: 0.9, scheduled_rate: null }, Sand: { current_rate: 1.1, scheduled_rate: null }, Chemical: { current_rate: 4.4, scheduled_rate: null }, Cement: { current_rate: 309, scheduled_rate: null } };
    if (path === "/rates/history") return { history: [] };
    if (path === "/recipe") return { Flyash: { qty_per_mix: 300, unit: "kg" }, Sand: { qty_per_mix: 200, unit: "kg" }, Chemical: { qty_per_mix: 12, unit: "L" }, Cement: { qty_per_mix: 1, unit: "packets" } };
    if (path === "/charges") return { charges: { Labour: 0.8, Loading: 0.3, Union: 0.1 }, total_making_charge: 1.2 };
    if (path === "/charges/history") return { history: [] };
    if (path === "/fixed-monthly-charges") return { rent_amount: { label: "Rent", value: 25000 }, manager_salary_amount: { label: "Manager salary", value: 30000 }, electricity_default: { label: "Electricity", value: 12000 }, water_default: { label: "Water", value: 6000 } };
    if (path === "/reports/production-costs") return { month: "September 2026", days_worked: 24, bricks: 87360, mixes: 480, average_bricks_per_mix: 182, material_cost: 245000, making_cost: 104832, misc_expenses: 12400, overhead: { rent: 25000, manager_salary: 30000, electricity: 12000, water: 6000, electricity_is_default: true, water_is_default: true } };
    if (path.startsWith("/admin/dashboard/") || path === "/stock-overview") return path.includes("fun-facts") ? { facts: ["Best production day: 4,120 bricks", "Average output: 182 bricks per mix"] } : path.includes("today-activity") ? [] : [];
    if (path === "/daily-report/delivery-settings") return { whatsapp_number: "+919876543210", email: "reports@example.test", send_time: "20:00", auto_send_enabled: false };
    if (path === "/daily-report/summary-text") return { whatsapp_number: "+919876543210", text: "Demo daily report: 3,640 bricks produced." };
    if (path === "/daily-report/email" || path === "/daily-report/whatsapp-number" || path === "/daily-report/schedule") return { message: "Demo setting saved" };
    if (path === "/manager/utility-bills" || path === "/order-planning" || path === "/profit-calculator" || path === "/max-producible") return {};
    if (method !== "GET") return { message: "Demo change saved", old_value: 0, new_value: body?.new_value ?? body?.amount ?? 0, label: "Demo setting" };
    return dashboard;
  }

  window.apiFetch = async function (path, options = {}) {
    const method = options.method || "GET";
    if (path === "/login" && (!options.body?.password || !options.body?.username)) throw new Error("Enter a username and password.");
    await new Promise((resolve) => setTimeout(resolve, method === "GET" ? 120 : 260));
    if (path === "/login") {
      const data = response(path, method, options.body);
      sessionStorage.setItem("access_token", data.access_token);
      sessionStorage.setItem("username", data.username);
      sessionStorage.setItem("role", data.role);
    }
    return json(response(path, method, options.body));
  };

  window.fetchPDF = async function () {
    return new Blob(["NEO BRICKS DEMO REPORT\nThis is a redesign preview document."], { type: "application/pdf" });
  };
})();