"""MinerU HTTP 客户端: 远程 mineru.net API v4(批量) 与本地 docker mineru-api 双实现。

- RemoteMinerUClient: ``POST /file-urls/batch`` 申请预签名上传链接 → PUT 上传
  (系统自动建解析任务) → 轮询 ``GET /extract-results/batch/{batch_id}`` →
  下载结果 zip。支持一次批量提交多个文件(单批上限 200)。
- LocalMinerUClient: ``POST {local_endpoint}`` multipart 上传, 同步返回结果
  zip 流(2.x 契约, 端点可配置以适配其他版本)。

两者统一暴露 ``parse(file) -> zip bytes`` 与 ``parse_batch(files) -> [zip bytes]``。
"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from module_office.utils.file_parase.mineru.config import MinerUConfig

logger = logging.getLogger(__name__)

# 远程单批文件数上限(官方限制 200)
_MAX_BATCH_FILES = 200
# 远程轮询时视为终态的失败/完成状态
_STATE_DONE = "done"
_STATE_FAILED = "failed"


class MinerUError(RuntimeError):
    """MinerU 解析异常(请求失败/解析失败/超时)。"""


class BaseMinerUClient(ABC):
    """MinerU 客户端基类: 统一 parse / parse_batch 接口。"""

    def __init__(self, cfg: MinerUConfig):
        self.cfg = cfg

    async def parse(self, file: Path) -> bytes:
        """解析单个文件, 返回结果 zip 字节流。"""
        return (await self.parse_batch([file]))[0]

    @abstractmethod
    async def parse_batch(self, files: list[Path]) -> list[bytes]:
        """批量解析, 返回与 files 等序的结果 zip 字节列表。"""
        raise NotImplementedError


class RemoteMinerUClient(BaseMinerUClient):
    """mineru.net 远程 API v4 客户端(默认)。

    鉴权: ``Authorization: Bearer <token>``。文件上传走预签名 PUT 链接
    (24h 有效, 上传时**不设 Content-Type**, 上传完成系统自动提交解析任务)。
    """

    def __init__(self, cfg: MinerUConfig):
        super().__init__(cfg)
        if not cfg.token:
            raise MinerUError("MinerU 远程模式缺少 token, 请配置 mineru.token")
        self._headers = {"Authorization": f"Bearer {cfg.token}"}

    async def parse_batch(self, files: list[Path]) -> list[bytes]:
        """批量解析: 按 200 个/批分片提交, 汇总返回等序 zip 列表。"""
        if not files:
            return []
        results: list[bytes] = []
        for start in range(0, len(files), _MAX_BATCH_FILES):
            batch = files[start : start + _MAX_BATCH_FILES]
            results.extend(await self._parse_one_batch(batch))
        return results

    async def _parse_one_batch(self, files: list[Path]) -> list[bytes]:
        """单批流程: 申请链接 → 上传 → 轮询 → 下载 zip。"""
        base = self.cfg.remote_base_url
        async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
            # 1. 申请批量上传链接(data_id 记录原始序号, 用于结果对位)
            payload = {
                "enable_formula": self.cfg.enable_formula,
                "enable_table": self.cfg.enable_table,
                "model_version": self.cfg.model_version,
                "language": self.cfg.language,
                "is_ocr": self.cfg.is_ocr,
                "files": [
                    {"name": f.name, "data_id": str(idx), "is_ocr": self.cfg.is_ocr}
                    for idx, f in enumerate(files)
                ],
            }
            data = await self._request_data(client, "POST", f"{base}/file-urls/batch", json=payload)
            batch_id = data.get("batch_id")
            upload_urls: list[str] = data.get("file_urls") or []
            if not batch_id or len(upload_urls) != len(files):
                raise MinerUError(f"MinerU 返回上传链接异常: batch_id={batch_id}")

            # 2. 上传文件到预签名链接(不设 Content-Type, 由服务端推断)
            for file, url in zip(files, upload_urls):
                resp = await client.put(url, content=file.read_bytes())
                if resp.status_code >= 400:
                    raise MinerUError(f"MinerU 文件上传失败({resp.status_code}): {file.name}")

            # 3. 轮询批量结果
            extract_result = await self._wait_batch(client, base, batch_id)

            # 4. 下载结果 zip(按 data_id 还原输入顺序)
            by_data_id = {str(r.get("data_id")): r for r in extract_result}
            zips: list[bytes] = []
            for idx in range(len(files)):
                item = by_data_id.get(str(idx))
                if item is None or item.get("state") != _STATE_DONE:
                    err = (item or {}).get("err_msg") or "结果缺失"
                    raise MinerUError(f"MinerU 解析失败({files[idx].name}): {err}")
                zip_url = item.get("full_zip_url")
                if not zip_url:
                    raise MinerUError(f"MinerU 结果缺少 full_zip_url: {files[idx].name}")
                zips.append(await self._download(client, zip_url))
            return zips

    async def _wait_batch(self, client: httpx.AsyncClient, base: str, batch_id: str) -> list[dict]:
        """轮询批量解析结果直到全部完成/失败/超时, 返回 extract_result 列表。"""
        url = f"{base}/extract-results/batch/{batch_id}"
        deadline = time.monotonic() + self.cfg.poll_timeout
        while True:
            data = await self._request_data(client, "GET", url)
            results: list[dict] = data.get("extract_result") or []
            states = [str(r.get("state")) for r in results]
            if _STATE_FAILED in states:
                errs = [r.get("err_msg") for r in results if r.get("state") == _STATE_FAILED]
                raise MinerUError(f"MinerU 解析失败: {errs}")
            if results and all(s == _STATE_DONE for s in states):
                return results
            if time.monotonic() > deadline:
                raise MinerUError(
                    f"MinerU 解析超时({self.cfg.poll_timeout}s), batch_id={batch_id}, states={states}"
                )
            logger.debug("MinerU 批量任务 %s 进行中: %s", batch_id, states)
            await asyncio.sleep(self.cfg.poll_interval)

    async def _request_data(
        self, client: httpx.AsyncClient, method: str, url: str, json: dict | None = None
    ) -> dict:
        """发送带鉴权的 JSON 请求并校验响应, 返回 data 节。"""
        resp = await client.request(method, url, headers=self._headers, json=json)
        if resp.status_code >= 400:
            raise MinerUError(f"MinerU 接口请求失败({resp.status_code} {url}): {resp.text[:500]}")
        body = resp.json()
        if body.get("code") not in (0, "0"):
            raise MinerUError(f"MinerU 接口返回错误({url}): {body.get('msg') or body}")
        return body.get("data") or {}

    @staticmethod
    async def _download(client: httpx.AsyncClient, url: str) -> bytes:
        """下载结果 zip(预签名链接, 无需鉴权头)。"""
        resp = await client.get(url)
        if resp.status_code >= 400:
            raise MinerUError(f"MinerU 结果下载失败({resp.status_code}): {url}")
        return resp.content


class LocalMinerUClient(BaseMinerUClient):
    """本地 docker mineru-api 客户端(2.x 契约, 端点可配置)。

    ``POST {local_base_url}{local_endpoint}`` multipart 上传, 同步返回 zip 流。
    请求参数按 2.x web_api: is_ocr/lang/backend/return_content_list 等。
    """

    async def parse_batch(self, files: list[Path]) -> list[bytes]:
        """本地服务无批量端点, 逐文件顺序解析。"""
        url = f"{self.cfg.local_base_url}{self.cfg.local_endpoint}"
        results: list[bytes] = []
        async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
            for file in files:
                results.append(await self._parse_one(client, url, file))
        return results

    async def _parse_one(self, client: httpx.AsyncClient, url: str, file: Path) -> bytes:
        logger.info("MinerU 本地解析: %s -> %s", file.name, url)
        with file.open("rb") as fp:
            resp = await client.post(
                url,
                files={"file": (file.name, fp)},
                data={
                    "is_ocr": str(self.cfg.is_ocr).lower(),
                    "lang": self.cfg.language,
                    "backend": self.cfg.model_version,
                    "return_content_list": "true",
                    "return_middle_json": "false",
                    "return_figures": "false",
                },
            )
        if resp.status_code >= 400:
            raise MinerUError(f"MinerU 本地解析失败({resp.status_code}): {resp.text[:500]}")
        content = resp.content
        if not content.startswith(b"PK"):
            # 非 zip 响应: 多为参数/版本不匹配的错误 JSON
            raise MinerUError(f"MinerU 本地服务返回非 zip 结果: {content[:500].decode(errors='replace')}")
        return content


def build_client(cfg: MinerUConfig) -> BaseMinerUClient:
    """按配置构建客户端: mode=local 用本地服务, 其余(默认 remote)用远程 API。"""
    if cfg.mode == "local":
        logger.info("MinerU 使用本地部署: %s%s", cfg.local_base_url, cfg.local_endpoint)
        return LocalMinerUClient(cfg)
    logger.info("MinerU 使用远程 API: %s", cfg.remote_base_url)
    return RemoteMinerUClient(cfg)
