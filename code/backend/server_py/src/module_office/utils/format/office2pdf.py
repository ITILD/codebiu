"""OnlyOffice 文档转换客户端（异步）：支持同步转换、异步提交与状态查询。

所有 IO 均为非阻塞，可用 asyncio.gather 并发处理多个任务。
轮询逻辑由调用方实现（见 __main__ 中的 _poll_task 示例）。
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

import aiohttp
from jwt import encode


@dataclass
class ConvertStatus:
    """转换任务的当前状态。"""
    end_convert: bool
    percent: int = 0
    file_url: str | None = None
    file_type: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class ConvertTask:
    """异步转换任务句柄，保留 payload 以便后续查询状态。"""
    key: str
    payload: dict
    last_status: ConvertStatus

    @property
    def done(self) -> bool:
        return self.last_status.end_convert


class OfficeConvertClient:
    """异步 OnlyOffice ConvertService 客户端。

    推荐用 ``async with OfficeConvertClient(...) as client:`` 管理 session 生命周期。
    轮询逻辑不应放在客户端内，由调用方按需实现。
    """

    def __init__(
        self,
        server_host: str,
        jwt_secret: str,
        timeout: int = 60,
    ) -> None:
        self.server_host = server_host.rstrip("/")
        self.convert_url = f"{self.server_host}/ConvertService.ashx"
        self.jwt_secret = jwt_secret
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "OfficeConvertClient":
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    def _session_or_create(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    # ---------- 公开接口 ----------

    async def convert(
        self,
        source_url: str,
        source_type: str,
        output_path: str | Path,
        outputtype: str = "pdf",
        title: str | None = None,
    ) -> bool:
        """同步模式转换：await 一次请求直到完成并下载到 output_path。"""
        payload = self._build_payload(
            source_url, source_type, outputtype, title,
            async_mode=False, key=self._gen_key(),
        )
        status = await self._request(payload)
        if status.end_convert and status.file_url:
            return await self.download(status.file_url, output_path)
        print(f"同步转换未完成: endConvert={status.end_convert}, "
              f"percent={status.percent}, fileUrl={status.file_url}")
        return False

    async def submit(
        self,
        source_url: str,
        source_type: str,
        outputtype: str = "pdf",
        title: str | None = None,
        key: str | None = None,
    ) -> ConvertTask:
        """异步模式提交转换任务，立即返回任务句柄用于后续状态查询。

        OnlyOffice 没有独立的队列查询端点，需用相同 key 重新请求获取进度。
        """
        key = key or self._gen_key()
        payload = self._build_payload(
            source_url, source_type, outputtype, title, async_mode=True, key=key,
        )
        status = await self._request(payload)
        return ConvertTask(key=key, payload=payload, last_status=status)

    async def check_status(self, task: ConvertTask) -> ConvertStatus:
        """查询任务当前转换状态（用相同 key 重新请求获取最新进度）。"""
        task.last_status = await self._request(task.payload)
        return task.last_status

    async def download(self, file_url: str, output_path: str | Path) -> bool:
        """下载转换产物到本地。"""
        session = self._session_or_create()
        try:
            async with session.get(file_url) as resp:
                resp.raise_for_status()
                data = await resp.read()
            Path(output_path).write_bytes(data)
            return True
        except aiohttp.ClientError as e:
            print(f"下载文件失败: {e}")
            return False

    # ---------- 内部方法 ----------

    @staticmethod
    def _gen_key() -> str:
        # key 必须唯一，避免命中 OnlyOffice 缓存；加入 uuid 防止同秒并发冲突
        return f"conv_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    def _build_payload(
        self,
        source_url: str,
        source_type: str,
        outputtype: str,
        title: str | None,
        async_mode: bool,
        key: str,
    ) -> dict:
        payload: dict = {
            "async": async_mode,
            "filetype": source_type.lower(),
            "key": key,
            "outputtype": outputtype,
            "title": title or f"convert.{outputtype}",
            "url": source_url,  # OnlyOffice 容器将主动下载此 URL
        }
        # 将 JWT 放入请求体（推荐方式，避免反向代理丢失 Header）
        payload["token"] = encode(payload, self.jwt_secret, algorithm="HS256")
        return payload

    async def _request(self, payload: dict) -> ConvertStatus:
        """发送转换请求并按 Content-Type 解析（兼容 XML/JSON）。"""
        session = self._session_or_create()
        try:
            async with session.post(self.convert_url, json=payload) as resp:
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "").lower()
                if "xml" in content_type:
                    return self._parse_xml(await resp.text())
                return self._parse_json(await resp.json())
        except aiohttp.ClientError as e:
            print(f"请求转换接口失败: {e}")
        except (ValueError, ET.ParseError) as e:
            print(f"解析响应失败: {e}")
        return ConvertStatus(end_convert=False, raw={"error": "request_failed"})

    @staticmethod
    def _parse_xml(text: str) -> ConvertStatus:
        root = ET.fromstring(text)
        raw = {child.tag: (child.text or "") for child in root}
        return ConvertStatus(
            end_convert=(raw.get("EndConvert", "").strip().lower() == "true"),
            percent=int((raw.get("Percent") or "0").strip() or 0),
            file_url=(raw.get("FileUrl") or "").strip() or None,
            file_type=(raw.get("FileType") or "").strip() or None,
            raw=raw,
        )

    @staticmethod
    def _parse_json(result: dict) -> ConvertStatus:
        return ConvertStatus(
            end_convert=bool(result.get("endConvert")),
            percent=int(result.get("percent") or 0),
            file_url=result.get("fileUrl"),
            file_type=result.get("fileType"),
            raw=result,
        )


if __name__ == "__main__":
    # ================= 调用方示例（含轮询逻辑） =================
    # 轮询不属于客户端职责，这里仅作演示。生产中可换成事件回调、消息队列等。

    async def _poll_task(
        client: OfficeConvertClient,
        task: ConvertTask,
        interval: float = 2.0,
        max_wait: float = 120.0,
    ) -> ConvertStatus:
        """轮询任务直到完成或超时（调用方逻辑，非客户端方法）。"""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            status = await client.check_status(task)
            print(f"  轮询中: percent={status.percent}, endConvert={status.end_convert}")
            if status.end_convert:
                return status
            await asyncio.sleep(interval)
        print(f"  轮询超时（{max_wait}s）")
        return task.last_status


    async def _main() -> None:
        ONLYOFFICE_SERVER = "http://192.168.1.252:11000"
        SECRET = "qwer1234qwer1234qwer1234qwer1234"
        ONLINE_DOC_URL = "https://calibre-ebook.com/downloads/demos/demo.docx"

        async with OfficeConvertClient(ONLYOFFICE_SERVER, SECRET) as client:
            # 1) 同步转换
            print("=== 同步转换 ===")
            ok = await client.convert(
                source_url=ONLINE_DOC_URL,
                source_type="docx",
                output_path="./demo_converted.pdf",
            )
            print("同步转换：" + ("成功" if ok else "失败"))

            # 2) 异步提交 + 轮询（轮询逻辑在调用方）
            print("\n=== 异步转换 ===")
            task = await client.submit(
                source_url=ONLINE_DOC_URL,
                source_type="docx",
                outputtype="pdf",
                title="demo.docx",
            )
            print(f"已提交任务 key={task.key}, 初始: percent={task.last_status.percent}, "
                f"endConvert={task.last_status.end_convert}")
            final = await _poll_task(client, task, interval=2, max_wait=120)
            if final.end_convert and final.file_url:
                await client.download(final.file_url, "./demo_async.pdf")
                print("异步转换并下载完成")
            else:
                print(f"异步转换未完成: {final}")


    asyncio.run(_main())
