// 서버 API 호출 — 로그인 토큰은 이 기기의 localStorage 에만 둔다(이름 · 연락처 없음).
const KEY = 'ansan-neighbors-token';

export function getToken() {
  try { return localStorage.getItem(KEY) || ''; } catch { return ''; }
}
export function setToken(tok) {
  try { tok ? localStorage.setItem(KEY, tok) : localStorage.removeItem(KEY); } catch { /* 사생활 보호 모드 */ }
}

export class ApiError extends Error {
  constructor(status, code) { super(code || String(status)); this.status = status; this.code = code; }
}

export async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'Accept': 'application/json' };
  const tok = getToken();
  if (tok) headers['Authorization'] = 'Bearer ' + tok;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  let res;
  try {
    res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, 'network');
  }
  let data = null;
  try { data = await res.json(); } catch { /* 빈 응답 */ }
  if (!res.ok) throw new ApiError(res.status, data && data.error);
  return data;
}
