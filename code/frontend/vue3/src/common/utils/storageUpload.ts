// src/common/utils/storageUpload.ts
// 统一存储上传流程(内容级口径): 文件管理/知识库等业务共用一套 S3 直传/中转链路,
// 各业务仅提供自己的端点适配器(init/分片/完成/秒传), 记录口径独立互不干扰
// - direct(s3): init 凭证签发+预签名URL → 浏览器逐片直传对象存储 → complete 对账
// - proxy(local): ≤max_size 小文件 FormData 中转; 大文件分片经服务端中转

/** 分片信息 */
export interface MultipartPart {
  part_number: number;
  etag: string;
  size: number;
}

/** 上传模式(direct=预签名直传 / proxy=服务端中转) */
export interface StorageUploadMode {
  mode: 'direct' | 'proxy';
  /** 分片大小(字节) */
  part_size: number;
  /** 小文件直传上限(MB) */
  max_size: number;
}

/** 分片上传初始化响应(mode=direct 时 part_urls 与分片号一一对应) */
export interface StorageMultipartInit {
  is_existing: boolean;
  upload_id: string | null;
  part_size: number;
  mode: 'direct' | 'proxy';
  part_urls: string[] | null;
}

/** 业务端点适配器: 由各业务模块按自己的记录口径提供 */
export interface StorageUploadEndpoints<Ctx, R> {
  /** 查询上传模式(各业务自行缓存) */
  getMode: () => Promise<StorageUploadMode>;
  /** 初始化分片会话(秒传判断+内容登记+凭证签发) */
  init: (file: File, contentHash: string, ctx?: Ctx) => Promise<StorageMultipartInit>;
  /** proxy 模式分片中转(分片二进制经服务端保存) */
  uploadPart: (
    uploadId: string,
    partNumber: number,
    content: ArrayBuffer,
    ctx?: Ctx
  ) => Promise<MultipartPart>;
  /** 完成分片上传(服务端对账合并+按业务口径登记) */
  complete: (
    file: File,
    uploadId: string,
    parts: MultipartPart[],
    ctx?: Ctx
  ) => Promise<R>;
  /** 秒传登记(is_existing=true 时按业务口径直接建记录) */
  instant: (file: File, contentHash: string, ctx?: Ctx) => Promise<R>;
  /** proxy 模式小文件 FormData 直传(≤max_size, 可选; 不提供则统一走分片流程) */
  smallDirect?: (file: File, ctx?: Ctx) => Promise<R>;
}

/** 计算内容 SHA-256(十六进制) */
export const sha256Hex = async (file: Blob): Promise<string> => {
  const buf = await file.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
};

/** 预签名URL直传分片到对象存储(原生 fetch 不经服务端; 返回响应ETag) */
export const putToPresignedUrl = async (
  url: string,
  content: ArrayBuffer
): Promise<string> => {
  const resp = await fetch(url, {
    method: 'PUT',
    body: content,
    headers: { 'Content-Type': 'application/octet-stream' },
  });
  if (!resp.ok) {
    throw new Error(`直传分片失败: HTTP ${resp.status}`);
  }
  // ETag 需要对象存储桶 CORS 配置 ExposeHeaders 才可读取; 拿不到时由服务端对账阶段补齐
  return resp.headers.get('ETag') || '';
};

/** 创建统一存储上传器: 传入业务端点适配器, 返回 (file, ctx) => R 的上传函数 */
export const createStorageUploader = <Ctx = void, R = unknown>(
  endpoints: StorageUploadEndpoints<Ctx, R>
) => {
  return async (file: File, ctx?: Ctx): Promise<R> => {
    const mode = await endpoints.getMode();
    // proxy 模式小文件: 直接 FormData 中转(单请求, 免分片开销)
    if (
      mode.mode === 'proxy' &&
      endpoints.smallDirect &&
      file.size <= mode.max_size * 1024 * 1024
    ) {
      return endpoints.smallDirect(file, ctx);
    }
    const contentHash = await sha256Hex(file);
    // 初始化会话(秒传判断+内容登记+凭证签发)
    const init = await endpoints.init(file, contentHash, ctx);
    // 秒传: 相同内容已存在, 直接按业务口径建记录
    if (init.is_existing) {
      return endpoints.instant(file, contentHash, ctx);
    }
    const partSize = init.part_size;
    const total = Math.ceil(file.size / partSize);
    const parts: MultipartPart[] = [];
    if (init.mode === 'direct') {
      // direct: 逐片预签名直传对象存储, 数据面不经服务端
      const urls = init.part_urls || [];
      for (let i = 0; i < total; i++) {
        const blob = file.slice(i * partSize, Math.min((i + 1) * partSize, file.size));
        const etag = await putToPresignedUrl(urls[i], await blob.arrayBuffer());
        parts.push({ part_number: i + 1, etag, size: blob.size });
      }
    } else {
      // proxy: 逐片经服务端中转
      for (let i = 0; i < total; i++) {
        const blob = file.slice(i * partSize, Math.min((i + 1) * partSize, file.size));
        parts.push(
          await endpoints.uploadPart(init.upload_id!, i + 1, await blob.arrayBuffer(), ctx)
        );
      }
    }
    return endpoints.complete(file, init.upload_id!, parts, ctx);
  };
};
