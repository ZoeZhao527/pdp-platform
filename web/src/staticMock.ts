// Static demo mode: intercepts all fetch calls to /api/v1/* and returns mock data
// This allows the app to run without a backend server (for GitHub Pages deployment)
import mockData from "./staticMockData.json";

const MOCK_TOKEN = "static-demo-token";

// Pre-set auth so the app thinks we're logged in
if (!localStorage.getItem("pdp_token")) {
  localStorage.setItem("pdp_token", MOCK_TOKEN);
}
if (!localStorage.getItem("pdp_tenant_id")) {
  localStorage.setItem("pdp_tenant_id", "tenant-default");
}
// Set demo user as admin so all nav items (including dev console) show
if (!localStorage.getItem("pdp_user")) {
  localStorage.setItem("pdp_user", JSON.stringify({ id: "demo", username: "demo", display_name: "美业管理员", role: "admin" }));
}
// Set demo industry id to match mock tenant data
if (!localStorage.getItem("pdp_industry_id")) {
  localStorage.setItem("pdp_industry_id", "6601012c-44fb-4a58-8fab-3d27d7d12ace");
}

function mockResponse(path: string, method: string, body?: string) {
  // Handle login
  if (path === "/auth/login" && method === "POST") {
    return { token: MOCK_TOKEN, user: { id: "demo", username: "demo", display_name: "演示账号", role: "admin" } };
  }
  // Handle password change
  if (path === "/auth/password" && method === "POST") {
    return { ok: true };
  }
  // Handle instruction actions (approve/reject/accept/generate) - return success
  if (path.match(/\/platform\/instructions\/[^/]+\/(approve|reject|accept|generate|plan\/rebuild|plan\/pause)/) && method === "POST") {
    return { id: path.split("/")[3], status: "approved", tasks: 0 };
  }
  // Handle export endpoints - return empty blob
  if (path.includes("/export")) {
    return null;
  }
  // Handle campaign brief parse/upload - return empty
  if (path.includes("/campaign-brief")) {
    return { cards: [] };
  }
  // Handle chat instruction
  if (path === "/platform/instructions/chat" && method === "POST") {
    return { instruction_id: "static", title: "演示指令", content: body || "", params: {}, summary: "静态演示模式", status: "generated" };
  }
  // Handle create instruction
  if (path === "/platform/instructions" && method === "POST") {
    return { id: "static-new", status: "generated" };
  }
  // Handle strategy actions
  if (path.match(/\/strategies\/[^/]+\/(dispatch|toggle-managed)/) && method === "POST") {
    return { id: path.split("/")[2], status: "dispatched", managed: true };
  }
  if (path === "/strategies/promote-platform" && method === "POST") {
    return { id: "static", is_platform: true };
  }
  if (path === "/strategies/mutate" && method === "POST") {
    return { id: "static-mutant", name: "变异策略", note: "静态模式" };
  }
  if (path.match(/\/strategies\/candidates\/[^/]+\/(approve|reject)/) && method === "POST") {
    return { id: path.split("/")[3], status: "approved" };
  }
  if (path === "/strategies/recalc-effects" && method === "POST") {
    return { recalculated: 0 };
  }
  if (path === "/strategies/from-instruction/" && method === "POST") {
    return { id: "static", name: "策略" };
  }
  // Handle flywheel actions
  if (path === "/flywheel/signals" && method === "POST") {
    return { id: "static", status: "labeled" };
  }
  if (path === "/flywheel/signals/batch" && method === "POST") {
    return { added: 0 };
  }
  if (path.match(/\/flywheel\/signals\/[^/]+\/label/) && method === "POST") {
    return { id: "static", status: "labeled", scenario: "", tags: {} };
  }
  if (path.match(/\/flywheel\/demands\/[^/]+\/verify/) && method === "POST") {
    return { id: "static", verified: true };
  }
  if (path === "/flywheel/run-auto" && method === "POST") {
    return { collected: 0, labeled: 0, matched: 0 };
  }
  if (path === "/flywheel/trigger" && method === "POST") {
    return { cycle_id: "static", adopted: false };
  }
 if (path.match(/\/flywheel\/[^/]+\/adopt/) && method === "POST") {
    return { cycle_id: "static", adopted: true };
  }
  if (path === "/flywheel/matches/run" && method === "POST") {
    return { matched: 0, demands: 0 };
  }
  if (path === "/flywheel/products" && method === "POST") {
    return { id: "static", name: "产品" };
  }
  if (path.match(/\/flywheel\/products\/[^/]+/) && (method === "PUT" || method === "DELETE")) {
    return { ok: true };
  }
  if (path === "/flywheel/products/import" && method === "POST") {
    return { added: 0 };
  }
  // Handle execution todo actions
  if (path.match(/\/platform\/execution\/todos\/[^/]+/) && method === "PUT") {
    return { id: "static", channel: "朋友圈", due_at: null, content: "", status: "pending" };
  }
  if (path.match(/\/platform\/execution\/todos\/[^/]+\/dispatch/) && method === "POST") {
    return { id: "static", status: "dispatched" };
  }
  if (path === "/platform/execution/scheduler/run" && method === "POST") {
    return { dispatched: 0, missed: 0 };
  }
  // Handle send policy
  if (path === "/platform/send-policy" && method === "PUT") {
    return (mockData as any)["/platform/send-policy"] || { ok: true };
  }
  // Handle check channel
  if (path === "/platform/check-channel" && method === "POST") {
    return { ok: true, violations: [] };
  }
  // Handle feishu actions
  if (path === "/feishu/send" && method === "POST") {
    return { ok: true, message_id: "static" };
  }
  if (path === "/feishu/handle" && method === "POST") {
    return { ok: true, reply: "" };
  }
  if (path === "/feishu/test" && method === "POST") {
    return { ok: true, message: "静态模式" };
  }
  if (path === "/feishu/trigger-brief" && method === "POST") {
    return { ok: true };
  }
  if (path === "/feishu/config" && method === "PUT") {
    return { ok: true, detail: "静态模式" };
  }
  // Handle feedback
  if (path === "/platform/feedback" && method === "POST") {
    return { id: "static", action: "view" };
  }
  // Handle task status
  if (path.match(/\/platform\/tasks\/[^/]+\/status/) && method === "POST") {
    return { id: "static", status: "done" };
  }
  // Handle alert resolve
  if (path.match(/\/platform\/alerts\/[^/]+\/resolve/) && method === "POST") {
    return { id: "static", resolved: true };
  }
  // Handle report generate
  if (path === "/platform/reports/generate" && method === "POST") {
    return { id: "static", title: "演示报告" };
  }
  // Handle auth users
  if (path === "/auth/users" && method === "POST") {
    return { user: { id: "static", username: "new", role: "viewer" } };
  }
  // Handle dev brand actions
  if (path === "/dev/brands" && method === "POST") {
    return { id: "static", name: "品牌", code: "BRAND", status: "active" };
  }
  if (path.match(/\/dev\/brands\/[^/]+\/status/) && method === "PUT") {
    return { id: "static", status: "active" };
  }
  if (path.match(/\/dev\/brands\/[^/]+\/users/) && method === "POST") {
    return { id: "static", username: "new", role: "viewer", enabled: true };
  }
  if (path.match(/\/dev\/users\/[^/]+/) && method === "PUT") {
    return { id: "static", role: "viewer", enabled: true };
  }
  if (path === "/dev/platform-version/upgrade" && method === "POST") {
    return { version: "2.0", brands_updated: 0, details: [] };
  }
  // Handle industry templates
  if (path === "/platform/industry-templates" && method === "POST") {
    return { id: "static", kind: "template" };
  }
  if (path.match(/\/platform\/industry-templates\/[^/]+/) && method === "PUT") {
    return { id: "static", kind: "template", name: "模板" };
  }
  // Handle knowledge upload/delete
  if (path === "/knowledge/documents" && method === "POST") {
    return { id: "static", name: "文档", status: "indexed", chunk_count: 0 };
  }
  if (path.match(/\/knowledge\/documents\/[^/]+/) && method === "DELETE") {
    return { ok: true };
  }
  if (path.includes("/knowledge/search")) {
    return [];
  }
  // Handle channel update/test
  if (path.match(/\/admin\/channels\/[^/]+/) && method === "PUT") {
    return (mockData as any)["/admin/channels"]?.[0] || { id: "static", name: "渠道", enabled: true };
  }
  if (path.match(/\/admin\/channels\/[^/]+\/test/) && method === "POST") {
    return { ok: true, message_id: "static" };
  }
  // Handle LLM model create
  if (path === "/admin/llm/models" && method === "POST") {
    return { id: "static" };
  }
  // Handle strategy tags update
  if (path.match(/\/strategies\/[^/]+\/tags/) && method === "PUT") {
    return { id: "static", scenario_tags: [], audience_tags: [], channel_tags: [] };
  }
  // Handle strategy feedback
  if (path.match(/\/strategies\/[^/]+\/feedback/)) {
    return [];
  }
  if (path.match(/\/strategies\/[^/]+\/effect-breakdown/)) {
    return { total_runs: 0, success_rate: 0, metrics: {} };
  }
  // Handle webhook
  if (path === "/channels/mock/webhook" && method === "POST") {
    return { ok: true };
  }

  // Try exact match from mock data
  if (path in mockData) {
    return (mockData as any)[path];
  }

  // Try matching conversation messages
  const msgMatch = path.match(/\/conversations\/([^/]+)\/messages/);
  if (msgMatch) {
    const key = `/conversations/${msgMatch[1]}/messages`;
    if (key in mockData) return (mockData as any)[key];
    return [];
  }

  // Try matching platform reports
  const reportMatch = path.match(/\/platform\/reports\/([^/]+)/);
  if (reportMatch && !path.includes("generate")) {
    const key = `/platform/reports/${reportMatch[1]}`;
    if (key in mockData) return (mockData as any)[key];
    return { id: reportMatch[1], title: "报告", sections: [] };
  }

  // Try matching strategy individual
  const stratMatch = path.match(/\/strategies\/([^/]+)$/);
  if (stratMatch) {
    const all = (mockData as any)["/strategies"] as any[];
    if (Array.isArray(all)) {
      const found = all.find((s: any) => s.id === stratMatch[1]);
      if (found) return found;
    }
  }

  // Default: return empty
  return null;
}

const originalFetch = window.fetch;
window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : (input as Request).url;
  const method = init?.method || "GET";

  // Only intercept API calls
  if (!url.includes("/api/v1/")) {
    return originalFetch(input, init);
  }

  // Extract path after /api/v1
  const apiPath = url.substring(url.indexOf("/api/v1/") + 7);
  // Remove query string
  const cleanPath = apiPath.split("?")[0];

  const data = mockResponse(cleanPath, method, init?.body as string);

  if (data === null) {
    // For GET to unknown endpoints, return [] (safer for components expecting arrays)
    const fallback = method === "GET" ? [] : { ok: true };
    return new Response(JSON.stringify(fallback), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};
console.log("[Static Mock] API interceptor active - running in demo mode");
