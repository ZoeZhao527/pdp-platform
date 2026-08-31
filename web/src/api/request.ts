import axios, { type AxiosResponse } from "axios";
export type { AxiosRequestConfig } from "axios";

export const BASE = "/api/v1";

/** Backend unified response wrapper (used when present). */
export interface ApiResponse<T = unknown> {
  code: number;
  msg: string;
  data: T;
  timestamp: number;
}

export interface PageItem<T> {
  items: T[];
  total: number;
  pages: number;
  size: number;
  current: number;
}

export interface PageResponse<T> {
  code: number;
  msg: string;
  data: PageItem<T>;
  timestamp: number;
}

const friendly: Record<number, string> = {
  401: "登录已过期，请重新登录",
  403: "没有操作权限",
  404: "资源不存在",
  422: "参数格式不正确",
  429: "请求太频繁，请稍后重试",
  500: "服务器内部错误，请稍后重试",
  502: "网关错误，请稍后重试",
  503: "服务暂时不可用",
};

/** Toast stub — replaced by real Toast component when DOM is ready. */
let _toast: { error: (m: string) => void; success: (m: string) => void } = {
  error: (m: string) => console.error("[toast]", m),
  success: (m: string) => console.log("[toast]", m),
};
export function setToastHandler(h: typeof _toast) {
  _toast = h;
}

const http = axios.create({
  baseURL: BASE,
  timeout: 15000,
});

// ── Request interceptor: attach business headers ──
http.interceptors.request.use((config) => {
  if (!(config.data instanceof FormData)) {
    config.headers.set("Content-Type", "application/json");
  }
  const tenantId = localStorage.getItem("pdp_tenant_id");
  if (tenantId) config.headers.set("X-Tenant-Id", tenantId);
  const industryId = localStorage.getItem("pdp_industry_id");
  if (industryId) config.headers.set("X-Industry-Id", industryId);
  const token = localStorage.getItem("pdp_token");
  if (token) config.headers.set("Authorization", `Bearer ${token}`);
  return config;
});

// ── Response interceptor: unified error handling ──
http.interceptors.response.use(
  (response: AxiosResponse) => {
    // Binary responses pass through directly
    const ct = String(response.headers["content-type"] ?? "");
    if (ct.includes("application/octet-stream") || response.config.responseType === "blob") {
      return response;
    }
    // No unwrapping — return raw data to maintain backward compat with existing api.ts
    return response;
  },
  (error) => {
    if (axios.isCancel(error)) return Promise.reject(error);
    const status = error.response?.status as number | undefined;
    const detail = error.response?.data?.detail || error.response?.data?.message || "";
    const msg = (status !== undefined && friendly[status]) || detail || "网络异常，请稍后重试";
    if (status === 401) {
      localStorage.removeItem("pdp_token");
      window.location.href = "/login";
    }
    _toast.error(msg);
    return Promise.reject(error);
  },
);

// ── Generic typed helpers ──
interface Wrapped<T> {
  data: T;
  code: number;
  msg: string;
}

function unwrap<T>(data: unknown): T {
  const w = data as Wrapped<T> | null;
  if (w && typeof w === "object" && typeof w.code === "number" && w.code === 200) return w.data;
  return data as T;
}

export function get<T>(url: string, params?: object): Promise<T> {
  return http.get(url, { params }).then((r) => unwrap<T>(r.data));
}
export function post<T>(url: string, data?: unknown): Promise<T> {
  return http.post(url, data).then((r) => unwrap<T>(r.data));
}
export function put<T>(url: string, data?: unknown): Promise<T> {
  return http.put(url, data).then((r) => unwrap<T>(r.data));
}
export function del<T>(url: string, params?: object): Promise<T> {
  return http.delete(url, { params }).then((r) => unwrap<T>(r.data));
}

export default http;
