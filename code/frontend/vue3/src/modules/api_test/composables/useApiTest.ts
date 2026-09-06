/**
 * 接口测试执行引擎
 *
 * - 用 fetch 直连 /base_server 前缀(与 http_base_server 同源同前缀), 保留真实状态码用于判定
 * - 判定规则: 2xx 通过; 401/403/422 警告(登录/权限/参数); 404 按用例区分(资源型=警告, 否则=契约断裂);
 *   5xx/网络错误 = 失败
 * - 覆盖校验: 自动收集 src/modules/<模块>/api/ 下各文件的导出函数, 与清单 diff, 提示未收录的接口函数
 */
import { computed, reactive, ref } from 'vue';
import { useAuthStore } from '@/common/stores/auth';
import { API_CASES, caseKey, isAutoCase, type ApiCase } from '../data/cases';

/** 请求前缀(与 http_base_server 实例一致) */
const API_PREFIX = '/base_server';

/** 用例执行结果 */
export interface CaseResult {
  /** 判定级别 */
  level: 'running' | 'pass' | 'warn' | 'fail' | 'skip';
  /** HTTP 状态码(网络错误为 null) */
  statusCode: number | null;
  /** 判定说明 */
  message: string;
  /** 耗时(ms) */
  ms: number;
  /** 响应体预览 */
  snippet: string;
}

/** 自动收集的 api 模块(eager 打包, 均为小模块无体积压力) */
const apiModules = import.meta.glob('/src/modules/*/api/*.ts', { eager: true, import: '*' });

export function useApiTest() {
  /** 用例 key -> 执行结果 */
  const results = reactive<Record<string, CaseResult>>({});
  /** 是否正在批量执行 */
  const running = ref(false);
  /** 批量执行进度(已完成条数) */
  const progress = ref(0);

  /** 清单中可自动执行的用例 */
  const autoCases = computed(() => API_CASES.filter(isAutoCase));

  /** 覆盖校验: api 模块中已导出但未收录清单的接口函数 */
  const uncoveredFns = computed(() => {
    const covered = new Set(API_CASES.map((c) => `${c.file}#${c.fn}`));
    const missing: { file: string; fn: string }[] = [];
    for (const [file, exports] of Object.entries(apiModules)) {
      const fileName = file.replace(/\\/g, '/').split('/').pop() ?? file;
      for (const [name, value] of Object.entries(exports as Record<string, unknown>)) {
        // 只校验小写开头的接口函数(排除工具类/常量导出)
        if (typeof value === 'function' && /^[a-z]/.test(name) && !covered.has(`${fileName}#${name}`)) {
          missing.push({ file: fileName, fn: name });
        }
      }
    }
    return missing;
  });

  /** 统计: 各判定级别数量(skip 用例恒计为跳过) */
  const stats = computed(() => {
    let pass = 0;
    let warn = 0;
    let fail = 0;
    let skip = 0;
    for (const c of API_CASES) {
      const level = c.skip ? 'skip' : (results[caseKey(c)]?.level ?? 'idle');
      if (level === 'pass') pass++;
      else if (level === 'warn' || level === 'running') warn++;
      else if (level === 'fail') fail++;
      else if (level === 'skip') skip++;
    }
    return { pass, warn, fail, skip, idle: API_CASES.length - pass - warn - fail - skip };
  });

  /** 路径参数占位 {x} -> 0 (资源不存在时产生 404, 由 allow404 区分判定) */
  function resolvePath(path: string): string {
    return path.replace(/\{[^}]+\}/g, '0');
  }

  /** 执行单条用例并写入结果 */
  async function runCase(c: ApiCase): Promise<void> {
    const key = caseKey(c);
    if (c.skip) {
      results[key] = { level: 'skip', statusCode: null, message: c.note ?? '已跳过', ms: 0, snippet: '' };
      return;
    }
    results[key] = { level: 'running', statusCode: null, message: '请求中...', ms: 0, snippet: '' };
    const t0 = performance.now();
    try {
      // 与 http_base_server 一致地携带令牌(不启用 401 刷新重试, 保持判定真实)
      const token = useAuthStore().authState.tokens.access.token;
      const headers: Record<string, string> = {};
      if (token) headers.Authorization = `Bearer ${token}`;
      const resp = await fetch(`${API_PREFIX}${resolvePath(c.path)}`, {
        method: c.method,
        headers,
      });
      const ms = Math.round(performance.now() - t0);
      let snippet = '';
      try {
        snippet = (await resp.text()).slice(0, 500);
      } catch {
        // 响应体读取失败不影响判定
      }
      let level: CaseResult['level'];
      let message: string;
      if (resp.ok) {
        level = 'pass';
        message = '接口可用';
      } else if (resp.status === 401) {
        level = 'warn';
        message = '未登录或令牌过期';
      } else if (resp.status === 403) {
        level = 'warn';
        message = '无权限访问';
      } else if (resp.status === 404) {
        if (c.allow404) {
          level = 'warn';
          message = '资源不存在(路由可达)';
        } else {
          level = 'fail';
          message = '接口不存在(前后端契约断裂)';
        }
      } else if (resp.status === 422) {
        level = 'warn';
        message = '参数校验失败(需真实参数)';
      } else {
        level = 'fail';
        message = `服务器错误 ${resp.status}`;
      }
      results[key] = { level, statusCode: resp.status, message, ms, snippet };
    } catch (e) {
      results[key] = {
        level: 'fail',
        statusCode: null,
        message: e instanceof Error ? e.message : '网络错误',
        ms: Math.round(performance.now() - t0),
        snippet: '',
      };
    }
  }

  /** 批量执行全部自动用例(顺序执行, 可中断) */
  async function runAll(): Promise<void> {
    if (running.value) return;
    running.value = true;
    progress.value = 0;
    for (const c of autoCases.value) {
      if (!running.value) break; // 已被 stopAll 中断
      await runCase(c);
      progress.value++;
    }
    running.value = false;
  }

  /** 中断批量执行 */
  function stopAll(): void {
    running.value = false;
  }

  /** 清空结果 */
  function reset(): void {
    for (const key of Object.keys(results)) delete results[key];
    progress.value = 0;
  }

  return {
    cases: API_CASES,
    results,
    running,
    progress,
    autoCases,
    stats,
    uncoveredFns,
    runAll,
    stopAll,
    runCase,
    reset,
  };
}
