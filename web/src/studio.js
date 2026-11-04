import { reactive, ref, computed } from "vue";
export const db = reactive({ settings: {}, timelines: {} });
export const connectionError = ref("");
export const busy = ref(false);
export const projectId = ref(localStorage.getItem("catstudio-project") || "");
export const page = ref(location.hash.slice(1) || "dashboard");
window.addEventListener("hashchange", () => {
  page.value = location.hash.slice(1) || "dashboard";
});
export function nav(to, pid) {
  const stage = {
    brief: 1,
    research: 2,
    script: 3,
    assets: 4,
    models: 5,
    bindings: 5,
    review: 5,
    progress: 5,
    placement: 5,
    edit: 6,
    delivery: 6,
    retro: 7,
  }[to];
  const current = (db.project || []).find(
    (x) => x.id === (pid ?? projectId.value),
  );
  const previouslyConfirmed = (db.gate_event || []).some(
    (x) =>
      x.project_id === current?.id &&
      x.status === "confirmed" &&
      x.data.stage >= stage,
  );
  if (
    current &&
    stage &&
    stage > (current.data.stage || 1) &&
    !previouslyConfirmed
  ) {
    notify(
      "请先完成“" +
        [
          "人群简报",
          "素材调研",
          "剧本分镜",
          "数字资产",
          "视频生成",
          "剪辑交付",
          "数据复盘",
        ][(current.data.stage || 1) - 1] +
        "”关卡，再进入后续阶段。",
      "warning",
    );
    return false;
  }
  if (pid !== undefined) {
    projectId.value = pid;
    localStorage.setItem("catstudio-project", pid);
  }
  page.value = to;
  location.hash = to;
  window.scrollTo(0, 0);
  return true;
}
export const project = computed(() =>
  list("project").find((x) => x.id === projectId.value),
);
export const list = (kind, pid) =>
  (db[kind] || []).filter((x) => pid === undefined || x.project_id === pid);
export const own = (kind) => list(kind, projectId.value);
export const byId = (kind, id) => list(kind).find((x) => x.id === id);
export const clone = (obj) => JSON.parse(JSON.stringify(obj ?? {}));
export async function api(path, method = "GET", body) {
  const r = await fetch("/api" + path, {
    method,
    headers:
      body instanceof FormData ? {} : { "Content-Type": "application/json" },
    body:
      body === undefined
        ? undefined
        : body instanceof FormData
          ? body
          : JSON.stringify(body),
  });
  if (!r.ok) {
    let e;
    try {
      e = await r.json();
    } catch {
      e = { detail: "请求失败 " + r.status };
    }
    throw new Error(
      typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail),
    );
  }
  return r.json();
}
export async function refresh() {
  try {
    const data = await api("/state");
    Object.assign(db, data);
    connectionError.value = "";
    if (projectId.value && !project.value) projectId.value = "";
  } catch (e) {
    connectionError.value = "无法连接本地服务：" + e.message;
  }
}
export function notify(text, type = "success") {
  window.studioMessage({
    message: text,
    type,
    duration: type === "error" ? 6000 : 3000,
  });
}
export async function act(fn, message) {
  busy.value = true;
  try {
    const r = await fn();
    await refresh();
    if (message) notify(message);
    return r;
  } catch (e) {
    notify(e.message, "error");
    return null;
  } finally {
    busy.value = false;
  }
}
export async function save(kind, body, id) {
  return api(
    "/items/" + kind + (id ? "/" + id : ""),
    id ? "PUT" : "POST",
    body,
  );
}
export async function upload(file) {
  if (!file) throw new Error("请先选择文件");
  const fd = new FormData();
  fd.append("file", file);
  return api("/upload", "POST", fd);
}
export function fileUrl(id, download = false) {
  return "/files/" + id + (download ? "?download=true" : "");
}
export function download(id) {
  if (id) window.open(fileUrl(id, true), "_blank");
}
export const statuses = {
  binding: "待绑定",
  historical: "历史版本",
  draft: "草稿",
  active: "制作中",
  complete: "已完成",
  confirmed: "已确认",
  final: "已定稿",
  disabled: "停用",
  pending: "待检查",
  ready: "可提交",
  awaiting: "待回传",
  returned: "已回传",
  review: "待审片",
  selected: "已选用",
  backup: "备选",
  rejected: "已淘汰",
  checking: "检测中",
  checked: "自动检查通过",
  check_failed: "检查未通过",
  publishable: "可发布",
  enhanced: "已增强",
  failed: "失败",
  success: "已完成",
  unverified: "未核对",
  exported: "已导出",
  imported: "已导入",
};
export const label = (s) => statuses[s] || s;
export const yuan = (n) => "¥" + Number(n || 0).toFixed(2);
export const date = (s) =>
  s ? new Date(s).toLocaleString("zh-CN", { hour12: false }) : "尚未登记";
export const stages = [
  "人群简报",
  "素材调研",
  "剧本分镜",
  "数字资产",
  "视频生成",
  "剪辑交付",
  "数据复盘",
];
export const stagePages = [
  "brief",
  "research",
  "script",
  "assets",
  "models",
  "edit",
  "retro",
];
export const shotList = computed(() => db.timelines[projectId.value] || []);
export const spent = (pid) =>
  list("cost_entry", pid).reduce((a, x) => a + x.amount_fen / 100, 0);
export const selected = (shotId) =>
  list("candidate").find(
    (x) => x.shot_id === shotId && x.status === "selected",
  );
