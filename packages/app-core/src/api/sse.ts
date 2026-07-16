export type SSEHandler = (event: string, data: Record<string, unknown>) => void;

function parseSSEPart(part: string, onEvent: SSEHandler) {
  if (!part.trim()) return;
  let event = "message";
  let dataStr = "";
  for (const line of part.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7);
    if (line.startsWith("data: ")) dataStr = line.slice(6);
  }
  if (dataStr) onEvent(event, JSON.parse(dataStr) as Record<string, unknown>);
}

export function createSSEParser(onEvent: SSEHandler) {
  let buffer = "";
  return {
    feed(text: string) {
      buffer += text;
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) parseSSEPart(part, onEvent);
    },
    flush() {
      if (buffer.trim()) parseSSEPart(buffer, onEvent);
      buffer = "";
    },
  };
}

/** React Native fetch often has no ReadableStream body for SSE. */
export function isReactNative(): boolean {
  return typeof navigator !== "undefined" && navigator.product === "ReactNative";
}

function drainXHRText(xhr: XMLHttpRequest, parser: ReturnType<typeof createSSEParser>, lastLen: { n: number }) {
  const text = xhr.responseText || "";
  if (text.length <= lastLen.n) return;
  const chunk = text.slice(lastLen.n);
  lastLen.n = text.length;
  if (chunk) parser.feed(chunk);
}

function wrapHandlerForRN(onEvent: SSEHandler): SSEHandler {
  if (!isReactNative()) return onEvent;
  return (event, data) => {
    requestAnimationFrame(() => onEvent(event, data));
  };
}

export function streamSSEViaXHR(
  url: string,
  headers: Record<string, string>,
  onEvent: SSEHandler,
  body?: BodyInit | null,
  timeoutMs = 600_000,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const parser = createSSEParser(wrapHandlerForRN(onEvent));
    const lastLen = { n: 0 };

    xhr.open("POST", url, true);
    for (const [k, v] of Object.entries(headers)) {
      xhr.setRequestHeader(k, v);
    }
    xhr.timeout = timeoutMs;

    const pump = () => drainXHRText(xhr, parser, lastLen);

    xhr.onprogress = pump;
    xhr.onreadystatechange = () => {
      // iOS RN: onprogress may not fire until done — LOADING (3) streams incrementally
      if (xhr.readyState === 3 || xhr.readyState === 4) pump();
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        pump();
        parser.flush();
        resolve();
        return;
      }
      reject(new Error(`Stream failed (${xhr.status}): ${xhr.responseText || xhr.statusText}`));
    };

    xhr.onerror = () => reject(new Error("Stream failed: network error"));
    xhr.ontimeout = () =>
      reject(new Error("Stream failed: timed out — try again or check your PC API is running"));

    xhr.send(body ?? null);
  });
}

export async function streamSSEViaFetch(
  url: string,
  headers: Record<string, string>,
  onEvent: SSEHandler,
  init?: RequestInit,
): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    headers,
    ...init,
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`Stream failed (${res.status}): ${errText || res.statusText}`);
  }

  if (!res.body) {
    const text = await res.text();
    const parser = createSSEParser(onEvent);
    parser.feed(text);
    parser.flush();
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSSEParser(onEvent);

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    parser.feed(decoder.decode(value, { stream: true }));
  }
  parser.flush();
}
