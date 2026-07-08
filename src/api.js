export async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    },
    credentials: "same-origin",
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error || "请求失败");
    error.status = response.status;
    error.fields = payload.fields || {};
    throw error;
  }
  return payload;
}

export async function requireSession(roles = []) {
  try {
    const { user } = await api("/api/me");
    if (roles.length > 0 && !roles.includes(user.role)) {
      location.href = "/login.html";
      return null;
    }
    return user;
  } catch {
    location.href = "/login.html";
    return null;
  }
}
