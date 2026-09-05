// src/common/api/http.ts —— 全局 HTTP 客户端(基于 fetch, 自动携带会话令牌)

import { useAuthStore } from '@/common/stores/auth';

// // 定义基础响应类型
// interface ApiResponse<T = any> {
//   code: number;
//   data: T;
//   message: string;
// }

// 查询参数值类型(数字/布尔会自动转为字符串)
type QueryParamValue = string | number | boolean | undefined | null;

// 定义请求配置类型
interface RequestConfig extends RequestInit {
  apiPrefix?: string;
  timeout?: number;
  params?: Record<string, QueryParamValue>;
  /** 内部标记: 401 刷新令牌后重试的请求, 不再二次重试 */
  _retry?: boolean;
}

// 认证端点本身的 401 属于业务失败(密码错误/刷新令牌无效), 不做刷新重试
const AUTH_NO_RETRY_PATHS = [
  '/authorization/auth/login',
  '/authorization/auth/register',
  '/authorization/auth/refresh',
];

// 防止并发请求同时触发多次回登录跳转
let redirectingToLogin = false;

class HttpClient {
  // 构造函数
  private apiPrefix: string;
  private timeout: number;
  // 单飞刷新: 并发 401 共享同一次刷新令牌请求
  private refreshPromise: Promise<boolean> | null = null;

  constructor(config: RequestConfig = {}) {
    this.apiPrefix = config.apiPrefix || import.meta.env.VITE_API_PREFIX;
    this.timeout = config.timeout || 10000;
  }

  // 核心请求方法
  async request<T>(endpoint: string, config: RequestConfig = {}): Promise<T> {
    const url = this.buildURL(endpoint, config.params);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort('timeout'), this.timeout);

    try {
      // 请求拦截
      const requestConfig = this.requestInterceptor({
        ...config,
        signal: controller.signal,
      });

      let response = await fetch(url, requestConfig);

      // 401 处理: 访问令牌过期时用刷新令牌续期并重试一次(认证端点本身除外)
      if (response.status === 401 && !config._retry && !AUTH_NO_RETRY_PATHS.includes(endpoint)) {
        // 是否曾登录过(存在刷新令牌); 从未登录的 401 保持原有行为交由调用方处理
        const hadSession = this.hasRefreshToken();
        const refreshed = hadSession && (await this.tryRefreshToken());
        if (refreshed) {
          // 重试时 requestInterceptor 会读取新令牌
          const retryConfig = this.requestInterceptor({
            ...config,
            signal: controller.signal,
            _retry: true,
          });
          response = await fetch(url, retryConfig);
        } else if (hadSession) {
          // 登录过但刷新失败: 会话已彻底失效, 清空并引导重新登录
          this.forceReLogin();
        }
      }

      // 响应拦截
      return this.responseInterceptor<T>(response);
    } catch (error) {
      this.errorHandler(error);
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  // 请求拦截器
  private requestInterceptor(config: RequestConfig): RequestInit {
    const headers = new Headers(config.headers);

    // 从 Pinia 认证 store 中读取访问令牌，自动携带到请求头
    // 后端通过 OAuth2PasswordBearer 解析 Authorization: Bearer {token}
    try {
      const authStore = useAuthStore();
      const token = authStore.authState.tokens.access.token;
      if (token) {
        headers.append('Authorization', `Bearer ${token}`);
      }
    } catch {
      // Pinia 尚未初始化时静默跳过（如应用启动前的早期请求）
    }

    // // 默认 JSON 内容类型，但FormData除外
    if (!(config.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.append('Content-Type', 'application/json');
    }

    return {
      ...config,
      headers,
    };
  }

  // 是否存在刷新令牌(判断是否登录过; Pinia 未初始化时视为未登录)
  private hasRefreshToken(): boolean {
    try {
      return !!useAuthStore().authState.tokens.refresh.token;
    } catch {
      return false;
    }
  }

  // 单飞刷新入口: 并发 401 共享同一次刷新请求
  private tryRefreshToken(): Promise<boolean> {
    if (!this.refreshPromise) {
      this.refreshPromise = this.doRefreshToken().finally(() => {
        this.refreshPromise = null;
      });
    }
    return this.refreshPromise;
  }

  // 调用后端刷新接口续期访问令牌(直接 fetch, 避免与认证 api 模块形成循环依赖)
  private async doRefreshToken(): Promise<boolean> {
    try {
      const authStore = useAuthStore();
      const refreshToken = authStore.authState.tokens.refresh.token;
      if (!refreshToken) return false;
      const res = await fetch(`${this.apiPrefix}/authorization/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token_refresh: refreshToken }),
      });
      if (!res.ok) return false;
      // TokenResponseBase: { token, expires_in, token_id }
      const access = await res.json();
      if (!access?.token) return false;
      // 更新 store 中的访问令牌(persist 插件会自动持久化)
      authStore.authState.tokens.access = access;
      return true;
    } catch {
      return false;
    }
  }

  // 会话彻底失效: 清空认证状态并回到首页引导登录(与路由守卫约定一致)
  private forceReLogin() {
    try {
      useAuthStore().initAuthState();
    } catch {
      return; // Pinia 未初始化, 交由路由守卫处理
    }
    if (redirectingToLogin) return;
    redirectingToLogin = true;
    console.warn('登录会话已过期, 请重新登录');
    window.location.replace('/?login=1');
  }

  // 响应拦截器
  private async responseInterceptor<T>(response: Response) {
    if (!response.ok) {
      let msg = `HTTP error! status: ${response.status}`;
      try {
        const err = await response.json();
        if (typeof err.detail === 'string') msg = err.detail;
      } catch { }
      throw new Error(msg);
    }
    // 检查是否为 204 No Content 不需要返回任何实体内容
    if (response.status === 204) return null;

    const data = await response.json();

    return data; // 返回业务数据
  }

  // 错误处理
  private errorHandler(error: unknown) {
    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        console.error('Request timeout');
      } else {
        console.error('Request failed:', error.message);
      }
    }
  }

  // 构建完整 URL
  private buildURL(endpoint: string, params?: Record<string, QueryParamValue>): string {
    // 创建 URL 对象（使用当前域名作为基准）
    const url = new URL(`${this.apiPrefix}${endpoint}`, window.location.origin);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        // 跳过空值参数(undefined/null/空字符串)
        if (value === undefined || value === null || value === '') return;
        url.searchParams.append(key, String(value));
      });
    }

    return url.toString();
  }

  // 快捷方法
  get<T>(endpoint: string, config?: RequestConfig): Promise<T> {
    return this.request(endpoint, { method: 'GET', ...config });
  }

  post<T>(endpoint: string, body?: any, config?: RequestConfig): Promise<T> {
    // 对于FormData，不进行JSON序列化
    const requestBody = body instanceof FormData ? body : JSON.stringify(body);
    return this.request(endpoint, {
      method: 'POST',
      body: requestBody,
      ...config,
    });
  }

  put<T>(endpoint: string, body?: any, config?: RequestConfig): Promise<T> {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(body),
      ...config,
    });
  }

  delete<T>(endpoint: string, config?: RequestConfig): Promise<T> {
    return this.request(endpoint, { method: 'DELETE', ...config });
  }
}

// 创建单例实例
// export const http_base_server = new HttpClient({ apiPrefix: '/base_server' });
export const http_base_server = new HttpClient({ apiPrefix: '/base_server', timeout: 300000 });
