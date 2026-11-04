<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
import {
  PawPrint,
  LayoutDashboard,
  FolderOpen,
  Images,
  Clapperboard,
  Video,
  ChartNoAxesCombined,
  Settings2,
  Wallet,
  ChevronRight,
  Plus,
  ArrowLeft,
  ArrowRight,
  Upload,
  Download,
  Check,
  CheckCheck,
  Copy,
  Search,
  ExternalLink,
  FileText,
  Link,
  MessageSquare,
  ImagePlus,
  Sparkles,
  ShieldCheck,
  Clock,
  Info,
  MoreHorizontal,
  BookOpen,
  HardDrive,
  RefreshCw,
  Trash2,
  GripVertical,
  Layers,
  Volume2,
  NotebookPen,
  HelpCircle,
} from "lucide-vue-next";
import FormModal from "./FormModal.vue";
import RetentionChart from "./RetentionChart.vue";
import {
  db,
  connectionError,
  busy,
  projectId,
  page,
  project,
  list,
  own,
  byId,
  clone,
  api,
  refresh,
  act,
  save,
  upload,
  download,
  fileUrl,
  notify,
  nav,
  label,
  yuan,
  date,
  stages,
  stagePages,
  shotList,
  spent,
  selected,
} from "./studio";

const modal = ref(null),
  search = ref(""),
  filter = ref("all"),
  assetType = ref("all"),
  assetId = ref(""),
  shotId = ref(""),
  candidateId = ref(""),
  compareId = ref(""),
  frame = ref(0),
  globalAssets = ref(false),
  modelPanel = ref("profiles"),
  preview = ref(null),
  aiResult = ref(null),
  showAI = ref(false),
  saving = ref(""),
  srt = ref(""),
  editNotes = ref(""),
  csvData = ref(null),
  csvFileId = ref(""),
  csvMapping = ref({}),
  csvRelease = ref(""),
  csvPeriod = ref("发布后7天"),
  videoPlayer = ref(null),
  comparePlayer = ref(null),
  playlistIndex = ref(0);
let timer,
  autoTimer,
  autosaving = false;
const briefForm = ref({}),
  generation = ref({}),
  llmText = ref({}),
  llmVision = ref({}),
  budget = ref({ monthly_cap: 500, pause: true });
const csvRow = ref(0),
  aiDraft = ref(""),
  commentImport = ref(null),
  commentColumns = ref([]),
  commentTextColumn = ref(""),
  commentLikesColumn = ref(""),
  assetCompareId = ref("");
const tagsText = computed({
  get: () => briefForm.value.tags?.join("、") || "",
  set: (v) =>
    (briefForm.value.tags = v
      .split(/[,，、]/)
      .map((x) => x.trim())
      .filter(Boolean)),
});
watch(aiResult, (a) => {
  if (a) aiDraft.value = JSON.stringify(a.result, null, 2);
});
const activeBrief = computed(() => own("brief")[0]);
const activeShot = computed(
  () => shotList.value.find((x) => x.id === shotId.value) || shotList.value[0],
);
const activeAsset = computed(
  () => list("asset").find((x) => x.id === assetId.value) || assets.value[0],
);
const assets = computed(() =>
  list("asset").filter(
    (x) =>
      (globalAssets.value ||
        x.project_id === projectId.value ||
        x.project_id === null) &&
      (assetType.value === "all" || x.data.type === assetType.value) &&
      (!search.value || x.name.includes(search.value)),
  ),
);
const versions = computed(() =>
  list("asset_version")
    .filter((x) => x.parent_id === activeAsset.value?.id)
    .sort((a, b) => b.version - a.version),
);
const avId = ref("");
const activeVersion = computed(
  () => versions.value.find((x) => x.id === avId.value) || versions.value[0],
);
const binds = computed(() =>
  own("shot_binding").filter((x) => x.shot_id === activeShot.value?.id),
);
const gens = computed(() =>
  own("generation_record")
    .filter((x) => x.shot_id === activeShot.value?.id)
    .sort((a, b) => b.created_at.localeCompare(a.created_at)),
);
const candidates = computed(() =>
  own("candidate").filter((x) => x.shot_id === activeShot.value?.id),
);
const candidate = computed(
  () =>
    candidates.value.find((x) => x.id === candidateId.value) ||
    candidates.value.at(-1),
);
const compareCandidate = computed(() =>
  candidates.value.find((x) => x.id === compareId.value),
);
const finals = computed(() =>
  own("final_cut").sort((a, b) => b.created_at.localeCompare(a.created_at)),
);
const finalId = ref("");
const activeFinal = computed(
  () => finals.value.find((x) => x.id === finalId.value) || finals.value[0],
);
const reviewChecks = ref({
    identity: false,
    contact: false,
    prop: false,
    continuity: false,
  }),
  finalChecks = ref({ motion: false, audio: false, subtitle: false }),
  issue = ref(""),
  issueTime = ref(0);
const bindingSelections = ref({});
const releaseId = ref("");
const metricSnapshotId = ref("");
const activeRelease = computed(
  () =>
    own("release").find((x) => x.id === releaseId.value) ||
    own("release").at(-1),
);
const metrics = computed(
  () =>
    own("metric_snapshot").find(
      (x) =>
        x.id === metricSnapshotId.value &&
        x.parent_id === activeRelease.value?.id,
    ) ||
    own("metric_snapshot")
      .filter((x) => x.parent_id === activeRelease.value?.id)
      .at(-1),
);
const points = computed(() =>
  own("retention_point").filter((x) => x.parent_id === metrics.value?.id),
);
const retroForm = ref({
  observation: "",
  hypothesis: "",
  evidence: "",
  status: "待验证",
  exp_goal: "",
  exp_keep: "",
  exp_change: "",
});
const projects = computed(() =>
  list("project")
    .filter(
      (x) =>
        (!search.value || x.name.includes(search.value)) &&
        (filter.value === "all" || x.status === filter.value),
    )
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
);
const sourceFilter = ref("全部平台"),
  timeFilter = ref(0),
  contentFilter = ref("all");
const filteredReferences = computed(() =>
  own("reference").filter(
    (x) =>
      (filter.value === "all" ||
        (filter.value === "cited" && x.data.is_cited) ||
        (filter.value === "starred" && x.data.is_starred)) &&
      (!search.value || x.name.includes(search.value)) &&
      (sourceFilter.value === "全部平台" ||
        x.data.platform === sourceFilter.value) &&
      (!Number(timeFilter.value) ||
        Date.now() - new Date(x.created_at).getTime() <
          Number(timeFilter.value) * 86400000) &&
      (contentFilter.value === "all" ||
        (contentFilter.value === "screenshots" &&
          x.data.screenshot_file_ids?.length) ||
        (contentFilter.value === "links" && x.data.url)),
  ),
);

const currentStage = computed(() => project.value?.data.stage || 1);
const subpages = {
  models: ["models", "bindings", "review", "progress", "placement"],
  edit: ["edit", "delivery"],
};
const titles = {
  dashboard: "项目工作台",
  projects: "视频项目",
  brief: "新建视频项目",
  research: "素材调研与选题",
  script: "剧本与分镜",
  assets: "项目数字资产",
  models: "模型选择与生成设置",
  bindings: "单镜素材绑定",
  review: "提交与审片",
  placement: "商品植入",
  progress: "镜头进度",
  edit: "剪辑准备",
  delivery: "成片与交付",
  retro: "数据复盘",
  compare: "跨视频对比",
  settings: "设置与模型档案",
  costs: "预算与费用流水",
  library: "全局数字资产库",
};
const subtitles = {
  dashboard: "从一个好选题，到一条可发布的萌宠视频。",
  brief: "先确定拍给谁看，再让 AI 帮你讲好故事。",
  research: "从真实生活的共鸣里，找到下一条猫咪故事。",
  script: "先确认故事，再把每一镜变成可执行的拍摄计划。",
  assets: "把角色、场景、服化道和声音，变成可复用的数字资产。",
  models: "核对官网模型档案，为每一镜安排合适的生成方式。",
  bindings: "固定素材版本，带着准确的提示词和上传顺序去官网。",
  review: "在官网生成，回到这里看动作、审候选、记花费。",
  progress: "看清每一镜的进度，下一步操作有据可循。",
  edit: "把选用镜头、声音要求和字幕，一起带到剪映。",
  delivery: "回传剪映成片，完成检测、试听和交付归档。",
  retro: "看懂哪里留住了观众，把观察变成下一条实验。",
  compare: "并列查看真实指标与统计窗口，追踪每一条单变量实验。",
  settings: "模型能力以官网核对为准，文本 AI 单独配置。",
  costs: "实际花费来自逐条记账，估算与待核价费用分别标明。",
  projects: "所有猫咪故事，都从一份清晰的创作简报开始。",
  library: "保留稳定的角色和资产，让下一条创作少一些重复。",
};
const types = [
  { value: "CHAR", label: "角色" },
  { value: "COST", label: "配饰" },
  { value: "SCN", label: "场景" },
  { value: "PROP", label: "道具" },
  { value: "VOICE", label: "声音" },
  { value: "SFX", label: "音效" },
  { value: "BGM", label: "音乐" },
  { value: "PROD", label: "商品" },
];
const typeLabel = (t) => types.find((x) => x.value === t)?.label || t;
const projectRequired = computed(
  () =>
    ![
      "dashboard",
      "projects",
      "settings",
      "costs",
      "library",
      "compare",
    ].includes(page.value),
);
const activeModels = computed(() =>
  list("model_profile").filter((x) => x.data.kind === "video"),
);
const pending = computed(() =>
  list("generation_record").filter((x) => x.status === "awaiting"),
);
const monthlySpend = computed(() =>
  list("cost_entry")
    .filter(
      (x) => x.created_at.slice(0, 7) === new Date().toISOString().slice(0, 7),
    )
    .reduce((a, x) => a + x.amount_fen / 100, 0),
);
const selectedCount = computed(
  () => shotList.value.filter((x) => selected(x.id)).length,
);
const reviewChecklist = [
  { value: "identity", label: "毛色与资产一致" },
  { value: "contact", label: "爪与道具接触自然" },
  { value: "prop", label: "道具形状与位置稳定" },
  { value: "continuity", label: "首尾状态可衔接" },
];
const ff = async () => {
  await refresh();
  if (!project.value && list("project").length) {
    projectId.value = list("project")[0].id;
    localStorage.setItem("catstudio-project", projectId.value);
  }
};
function openForm(title, fields, values, submit, description = "") {
  modal.value = {
    title,
    fields,
    values,
    description,
    submit: async (v) => {
      await submit(v);
      await refresh();
      notify("已保存");
    },
  };
}
const field = (key, label, type = "text", extra = {}) => ({
  key,
  label,
  type,
  ...extra,
});
async function newProject() {
  openForm(
    "新建视频项目",
    [
      field("name", "项目名称", "text", { required: true, maxlength: 60 }),
      field("source_project_id", "从已有项目复用简报与资产（可选）", "select", {
        options: list("project").map((x) => ({ value: x.id, label: x.name })),
      }),
    ],
    { name: "" },
    async (v) => {
      const p = await api("/projects", "POST", v);
      nav("brief", p.id);
      await refresh();
      syncForms();
    },
  );
}
function syncForms() {
  if (activeBrief.value) briefForm.value = clone(activeBrief.value.data);
  generation.value = {
    default_model_id: project.value?.data.default_model_id || "",
    ...(project.value?.data.generation_settings || {
      mode: "参考生视频",
      resolution: "720p",
      candidates: 1,
      audio_strategy: "后期补充",
    }),
  };
  editNotes.value = project.value?.data.edit_notes || "";
  srt.value = project.value?.data.srt || "";
  const r = own("retro").at(-1);
  retroForm.value = r
    ? { ...clone(r.data), status: r.status }
    : {
        observation: "",
        hypothesis: "",
        evidence: "",
        status: "待验证",
        exp_goal: "",
        exp_keep: "",
        exp_change: "",
      };
}
watch([page, projectId], async () => {
  filter.value = "all";
  search.value = "";
  shotId.value = "";
  preview.value = null;
  syncForms();
  if (["edit", "delivery"].includes(page.value) && project.value) {
    const r = await api("/projects/" + projectId.value + "/srt");
    srt.value = r.srt;
  }
  if (page.value === "settings") {
    llmText.value = clone(
      db.settings.llm_text || {
        provider: "openai",
        base_url: "https://api.openai.com/v1",
        model: "",
      },
    );
    llmVision.value = clone(
      db.settings.llm_vision || {
        provider: "openai",
        base_url: "https://api.openai.com/v1",
        model: "",
      },
    );
  }
  if (page.value === "library") globalAssets.value = true;
  else if (page.value === "assets") globalAssets.value = false;
});
watch(
  () => activeShot.value?.id,
  () => {
    preview.value = null;
    bindingSelections.value = Object.fromEntries(
      binds.value.map((x) => [x.id, x.data.asset_version_id || ""]),
    );
    candidateId.value = "";
    compareId.value = "";
  },
);
watch(
  () => candidate.value?.id,
  () => {
    reviewChecks.value = {
      identity: false,
      contact: false,
      prop: false,
      continuity: false,
    };
    issue.value = "";
    frame.value = 0;
  },
);
watch(
  () => activeFinal.value?.id,
  () => {
    finalChecks.value = clone(
      activeFinal.value?.data.manual_checks || {
        motion: false,
        audio: false,
        subtitle: false,
      },
    );
  },
);
watch(
  briefForm,
  () => {
    if (page.value !== "brief" || !activeBrief.value) return;
    clearTimeout(autoTimer);
    saving.value = "尚未保存";
    autoTimer = setTimeout(saveBrief, 1200);
  },
  { deep: true },
);
async function saveBrief() {
  if (!activeBrief.value) return;
  if (autosaving) {
    while (autosaving) await new Promise((r) => setTimeout(r, 50));
    return saveBrief();
  }
  const snap = JSON.stringify(briefForm.value);
  if (snap === JSON.stringify(activeBrief.value.data)) {
    saving.value = "已保存";
    return;
  }
  autosaving = true;
  saving.value = "保存中…";
  try {
    await save(
      "brief",
      { data: clone(briefForm.value), revision: activeBrief.value.revision },
      activeBrief.value.id,
    );
    await refresh();
    saving.value = "已保存";
  } catch (e) {
    saving.value = "保存失败";
    notify(e.message, "error");
  } finally {
    autosaving = false;
  }
}
async function confirmStage(n) {
  clearTimeout(autoTimer);
  if (n === 1) await saveBrief();
  await act(async () => {
    await api("/projects/" + projectId.value + "/gate/" + n, "POST");
    await refresh();
    nav(stagePages[Math.min(n, 6)]);
    syncForms();
  }, "阶段已确认");
}
async function remove(kind, id) {
  try {
    await window.studioConfirm(
      "此操作将归档该记录。已被引用的资产会被保护，历史生成记录不会删除。",
    );
    await act(() => api("/items/" + kind + "/" + id, "DELETE"), "已归档");
  } catch {}
}
function referenceForm() {
  openForm(
    "导入对标链接",
    [
      field("url", "原始链接", "url", { required: true, wide: true }),
      field("title", "标题", "text", { required: true }),
      field("platform", "平台", "select", {
        options: ["抖音", "小红书", "其他"],
      }),
      field("likes", "点赞数", "number", { min: 0 }),
      field("duration_s", "时长（秒）", "number", { min: 0 }),
      field("is_cited", "引用为共鸣证据", "checkbox"),
    ],
    { platform: "其他", likes: 0, duration_s: 0, is_cited: true },
    (v) =>
      save("reference", {
        project_id: projectId.value,
        name: v.title,
        data: v,
      }),
    "仅登记链接，不抓取页面或下载他人视频。",
  );
}
function commentForm() {
  openForm(
    "手录共鸣评论",
    [
      field("text", "评论文字", "textarea", { required: true, wide: true }),
      field("reference_id", "来源素材", "select", {
        options: own("reference").map((x) => ({ value: x.id, label: x.name })),
      }),
      field("likes", "点赞数", "number", { min: 0 }),
    ],
    { likes: 0 },
    (v) =>
      save("evidence", {
        project_id: projectId.value,
        parent_id: v.reference_id || null,
        name: v.text.slice(0, 20),
        data: { text: v.text, likes: v.likes, source: "手录" },
      }),
    "只保存评论文字与点赞数，不登记昵称或头像。",
  );
}
function screenshotForm() {
  openForm(
    "上传截图并登记",
    [
      field("file", "视频页或评论截图", "file", {
        required: true,
        accept: "image/*",
        wide: true,
      }),
      field("title", "素材标题", "text", { required: true }),
      field("url", "来源链接", "url"),
      field("recognize", "上传后使用多模态 LLM 识别", "checkbox"),
    ],
    {},
    async (v) => {
      const f = await upload(v.file);
      const r = await save("reference", {
        project_id: projectId.value,
        name: v.title,
        data: {
          title: v.title,
          url: v.url || "",
          screenshot_file_ids: [f.id],
          is_cited: true,
        },
      });
      if (v.recognize) await askAI("screenshot", { reference_id: r.id }, f.id);
    },
  );
}
function reuseTopic() {
  openForm(
    "从选题库复用方向",
    [
      field("direction_id", "选题方向", "select", {
        required: true,
        options: list("story_direction")
          .filter((x) => x.data.in_library)
          .map((x) => ({
            value: x.id,
            label:
              x.name +
              " · " +
              (byId("project", x.project_id)?.name || "历史项目"),
          })),
      }),
    ],
    {},
    (v) => api("/projects/" + projectId.value + "/reuse-direction", "POST", v),
    "复制方向及其引用的素材/评论，保留原始出处；复用后由你重新选择与确认。",
  );
}
function directionForm(obj) {
  const v = obj?.data || {};
  openForm(
    "故事方向",
    [
      field("title", "方向标题", "text", { required: true, wide: true }),
      field("resonance", "共鸣点", "textarea", { required: true }),
      field("cat_acting", "猫咪演法", "textarea", { required: true }),
      field("emotion_landing", "情绪落点", "textarea"),
      field("reference_id", "引用素材", "select", {
        options: own("reference").map((x) => ({ value: x.id, label: x.name })),
      }),
      field("is_selected", "选为当前方向", "checkbox"),
    ],
    {
      ...v,
      title: obj?.name || v.title || "",
      reference_id: v.cited_reference_ids?.[0],
      is_selected: v.is_selected ?? true,
    },
    (x) =>
      save(
        "story_direction",
        {
          project_id: projectId.value,
          name: x.title,
          data: {
            ...x,
            origin: "用户",
            cited_reference_ids: x.reference_id ? [x.reference_id] : [],
            cited_evidence_ids: v.cited_evidence_ids || [],
          },
        },
        obj?.id,
      ),
  );
}
function scriptForm(obj) {
  openForm(
    "剧情稿",
    [
      field("summary", "剧情正文", "textarea", {
        required: true,
        wide: true,
        rows: 8,
      }),
      field("emotion_landing", "情绪落点", "textarea", { wide: true }),
    ],
    obj?.data || {},
    (v) =>
      save(
        "script",
        {
          project_id: projectId.value,
          name: "剧情稿",
          status: "draft",
          data: v,
        },
        obj?.id,
      ),
  );
}
async function confirmScript(obj) {
  await act(
    () =>
      save(
        "script",
        { data: obj.data, status: "confirmed", revision: obj.revision },
        obj.id,
      ),
    "剧情已确认",
  );
}
const currentScript = computed(
  () =>
    own("script").sort((a, b) => b.created_at.localeCompare(a.created_at))[0],
);
function shotForm(sh) {
  const checks = sh?.data.checks || {};
  openForm(
    sh ? "编辑分镜" : "添加分镜",
    [
      field("title", "镜头名称", "text", { required: true }),
      field("duration_s", "镜头时长（秒）", "number", {
        required: true,
        min: 0.1,
        max: 600,
      }),
      field("shot_size", "景别", "select", {
        options: ["远景", "全景", "中景", "近景", "特写"],
      }),
      field("angle", "视角", "select", {
        options: ["平视", "俯视", "低机位", "第一视角"],
      }),
      field("action", "单一主动作", "textarea", { required: true, wide: true }),
      field("end_state", "结束状态", "textarea"),
      field("line_text", "台词 / 心声", "textarea"),
      field("sound", "声音需求", "textarea"),
      field("prompt", "视频提示词", "textarea", {
        wide: true,
        rows: 4,
        help: "可引用 {{主体}}、{{场景}}、{{道具}}，导出时会替换成官网主体或图 n。",
      }),
      field("checklist", "镜头检查", "checks", {
        wide: true,
        options: [
          { value: "single", label: "单一主动作" },
          { value: "anatomy", label: "四脚与猫爪动作符合身体逻辑" },
          { value: "continuity", label: "前后状态衔接" },
        ],
      }),
    ],
    {
      title: sh?.name || "",
      duration_s: sh?.duration_s || 6,
      shot_size: "近景",
      angle: "平视",
      ...(sh?.data || {}),
      ...checks,
    },
    async (v) => {
      const body = {
        project_id: projectId.value,
        parent_id: currentScript.value?.id,
        name: v.title,
        duration_s: Number(v.duration_s),
        seq: sh?.seq ?? shotList.value.length,
        status: "draft",
        data: {
          ...v,
          checks: {
            single: !!v.single,
            anatomy: !!v.anatomy,
            continuity: !!v.continuity,
          },
        },
      };
      const r = await save("shot", body, sh?.id);
      if (!sh)
        for (const [i, slot] of ["主体", "场景", "道具"].entries())
          await save("shot_binding", {
            project_id: projectId.value,
            shot_id: r.id,
            parent_id: r.id,
            name: slot,
            seq: i,
            data: {
              slot,
              required: true,
              asset_version_id: null,
              with_accessories: slot === "主体",
            },
          });
    },
  );
}
async function moveShot(sh, diff) {
  const ids = shotList.value.map((x) => x.id),
    a = ids.indexOf(sh.id),
    b = a + diff;
  if (b < 0 || b >= ids.length) return;
  [ids[a], ids[b]] = [ids[b], ids[a]];
  await act(
    () => api("/projects/" + projectId.value + "/reorder", "POST", { ids }),
    "镜头顺序已更新",
  );
}
const dragId = ref("");
async function dropShot(sh) {
  if (!dragId.value || dragId.value === sh.id) return;
  const ids = shotList.value.map((x) => x.id);
  ids.splice(ids.indexOf(dragId.value), 1);
  ids.splice(ids.indexOf(sh.id), 0, dragId.value);
  await act(() =>
    api("/projects/" + projectId.value + "/reorder", "POST", { ids }),
  );
  dragId.value = "";
}
function assetForm() {
  openForm(
    "新建数字资产",
    [
      field("name", "资产名称", "text", { required: true }),
      field("type", "资产类型", "select", { required: true, options: types }),
      field("global", "设为全局可复用资产", "checkbox"),
      field("fur", "毛色分区 / 外观特征", "textarea"),
      field("pose", "姿态要求", "textarea"),
      field("accessory", "固定配饰", "select", {
        options: list("asset")
          .filter((x) => x.data.type === "COST")
          .map((x) => ({ value: x.id, label: x.name })),
      }),
      field("locked_traits", "锁定特征", "textarea", { wide: true }),
    ],
    {
      type: "CHAR",
      pose: "四脚站立，禁止拟人直立",
      global: page.value === "library",
    },
    async (v) => {
      const a = await save("asset", {
        project_id: v.global ? null : projectId.value,
        name: v.name,
        data: {
          type: v.type,
          consistency: { fur: v.fur, pose: v.pose },
          locked_traits: v.locked_traits,
        },
      });
      if (v.accessory)
        await save("asset_link", {
          parent_id: a.id,
          data: { accessory_asset_id: v.accessory },
        });
      assetId.value = a.id;
    },
  );
}
function versionForm() {
  const a = activeAsset.value;
  if (!a) return;
  openForm(
    "回传 " + a.name + " 新版本",
    [
      field("file", "官网生成的图片 / 音频", "file", {
        required: true,
        wide: true,
        accept: "image/*,audio/*",
      }),
      field("role", "图位 / 音频角色", "select", {
        required: true,
        options: ["三视图", "表情", "细节", "主图", "音频"],
      }),
      field("model_profile_id", "生成模型档案", "select", {
        options: list("model_profile").map((x) => ({
          value: x.id,
          label: x.name,
        })),
      }),
      field("source", "来源", "select", {
        required: true,
        options: ["AI生成", "自拍", "自录", "购买", "其他"],
      }),
      field("license_note", "来源与授权说明", "textarea", {
        wide: true,
        required: ["VOICE", "SFX", "BGM"].includes(a.data.type),
      }),
      field("prompt", "本次生图提示词", "textarea", { wide: true }),
      field("credits", "消耗积分", "number", { min: 0 }),
      field("amount_cny", "实际消耗人民币", "number", { min: 0 }),
    ],
    {
      role:
        a.data.type === "CHAR"
          ? "三视图"
          : ["VOICE", "SFX", "BGM"].includes(a.data.type)
            ? "音频"
            : "主图",
      source: "AI生成",
      credits: 0,
      amount_cny: 0,
      prompt: a.data.prompt || "",
    },
    async (v) => {
      const f = await upload(v.file);
      const n =
        list("asset_version").filter((x) => x.parent_id === a.id).length + 1;
      const av = await save("asset_version", {
        project_id: a.project_id,
        parent_id: a.id,
        name: a.name,
        version: n,
        status: "pending",
        data: {
          source: v.source,
          license_note: v.license_note,
          model_profile_id: v.model_profile_id,
          prompt: v.prompt,
        },
      });
      await save("asset_file", {
        project_id: a.project_id,
        parent_id: av.id,
        name: v.role,
        data: { file_id: f.id },
      });
      if (Number(v.amount_cny) || Number(v.credits))
        await save("cost_entry", {
          project_id: projectId.value,
          parent_id: av.id,
          name: "图片生成",
          amount_cny: v.amount_cny,
          data: { credits: v.credits, model_profile_id: v.model_profile_id },
        });
      avId.value = av.id;
    },
  );
}
function addAssetFile() {
  if (!activeVersion.value) return;
  const av = activeVersion.value;
  openForm(
    "补充版本图位",
    [
      field("file", "素材文件", "file", {
        required: true,
        accept: "image/*,audio/*",
      }),
      field("role", "图位", "select", {
        required: true,
        options: ["三视图", "表情", "细节", "主图", "音频"],
      }),
    ],
    { role: "表情" },
    async (v) => {
      const f = await upload(v.file);
      await save("asset_file", {
        project_id: av.project_id,
        parent_id: av.id,
        name: v.role,
        data: { file_id: f.id },
      });
    },
  );
}
const assetFiles = (av) =>
  list("asset_file").filter((x) => x.parent_id === av?.id);
function cover(a) {
  const vs = list("asset_version")
    .filter((x) => x.parent_id === a.id)
    .sort((x, y) => y.version - x.version);
  return assetFiles(vs[0])[0]?.data.file_id;
}
function subjectForm() {
  if (!activeVersion.value) return;
  const av = activeVersion.value;
  openForm(
    "登记官网主体名称",
    [
      field("model_profile_id", "模型档案", "select", {
        required: true,
        options: list("model_profile").map((x) => ({
          value: x.id,
          label: x.name,
        })),
      }),
      field("name", "官网主体名", "text", {
        required: true,
        help: "不包含 @。请保持与官网创建的主体名称完全一致。",
      }),
    ],
    {},
    (v) =>
      save("platform_subject", {
        project_id: av.project_id,
        parent_id: av.id,
        name: v.name,
        data: { model_profile_id: v.model_profile_id },
      }),
  );
}
async function finalizeAsset() {
  if (!activeVersion.value) return;
  await act(
    () =>
      save(
        "asset_version",
        {
          status: "final",
          revision: activeVersion.value.revision,
          data: activeVersion.value.data,
        },
        activeVersion.value.id,
      ),
    "资产版本已定稿，原有镜头绑定保持原版本",
  );
}
async function assignRequirement(bind, vid) {
  await act(
    () =>
      save(
        "shot_binding",
        { data: { ...bind.data, asset_version_id: vid || null } },
        bind.id,
      ),
    "需求绑定已保存",
  );
}
const finalizedVersions = computed(() =>
  list("asset_version").filter(
    (x) =>
      x.status === "final" &&
      list("asset").find(
        (a) =>
          a.id === x.parent_id &&
          (a.project_id === null || a.project_id === projectId.value),
      ),
  ),
);
const optionsForSlot = (slot) =>
  finalizedVersions.value.filter((v) =>
    (
      ({
        主体: ["CHAR"],
        场景: ["SCN"],
        道具: ["PROP", "PROD"],
        声音: ["VOICE", "SFX", "BGM"],
      })[slot] || []
    ).includes(byId("asset", v.parent_id)?.data.type),
  );
const versionLabel = (v) => {
  const a = byId("asset", v.parent_id);
  return `${a?.name || "资产"} · v${v.version} · ${typeLabel(a?.data.type)}`;
};
function modelForm(obj) {
  const d = obj?.data || {};
  openForm(
    obj ? "编辑模型档案" : "新增模型档案",
    [
      field("name", "模型名称", "text", { required: true }),
      field("site_url", "官网地址", "url", { required: true }),
      field("kind", "类型", "select", {
        options: [
          { value: "video", label: "视频" },
          { value: "image", label: "图片" },
        ],
        required: true,
      }),
      field("version", "官网实际版本", "text", { required: true }),
      field("modes", "支持模式（逗号分隔）", "text", { required: true }),
      field("durations", "时长档位（秒，逗号分隔）", "text"),
      field("resolutions", "分辨率（逗号分隔）", "text"),
      field("ratios", "画幅（逗号分隔）", "text"),
      field("max_ref_images", "参考图片上限", "number", { min: 0 }),
      field("max_audio", "音频参考上限", "number", { min: 0 }),
      field("credit_price", "每候选积分", "number", { min: 0 }),
      field("credit_to_cny", "每积分人民币", "number", {
        min: 0,
        step: 0.0001,
      }),
      field("verified_at", "官网核对日期", "date", { required: true }),
    ],
    {
      name: obj?.name || "",
      kind: "video",
      max_ref_images: 0,
      max_audio: 0,
      ...d,
      modes: (d.modes || []).join(","),
      durations: (d.durations || []).join(","),
      resolutions: (d.resolutions || []).join(","),
      ratios: (d.ratios || []).join(","),
    },
    (v) =>
      save(
        "model_profile",
        {
          name: v.name,
          status: "verified",
          data: {
            ...v,
            modes: v.modes
              .split(/[,，]/)
              .map((x) => x.trim())
              .filter(Boolean),
            durations: v.durations.split(/[,，]/).filter(Boolean).map(Number),
            resolutions: v.resolutions
              .split(/[,，]/)
              .map((x) => x.trim())
              .filter(Boolean),
            ratios: v.ratios
              .split(/[,，]/)
              .map((x) => x.trim())
              .filter(Boolean),
            credit_price: v.credit_price === "" ? null : Number(v.credit_price),
            credit_to_cny:
              v.credit_to_cny === "" ? null : Number(v.credit_to_cny),
            max_ref_images: Number(v.max_ref_images),
            max_audio: Number(v.max_audio),
          },
        },
        obj?.id,
      ),
    "请根据官网实际界面填写；系统不会把未核对的参数视为可用能力。",
  );
}
async function saveGeneration() {
  await act(
    () =>
      save(
        "project",
        {
          data: {
            ...project.value.data,
            default_model_id: generation.value.default_model_id,
            generation_settings: Object.fromEntries(
              Object.entries(generation.value).filter(
                ([k]) => k !== "default_model_id",
              ),
            ),
          },
        },
        projectId.value,
      ),
    "生成偏好已保存",
  );
}
async function shotModel(sh, value) {
  await act(
    () =>
      save(
        "shot",
        { data: { ...sh.data, model_profile_id: value || null } },
        sh.id,
      ),
    "逐镜设置已保存，请重新确认分镜关卡",
  );
}
async function loadPreview() {
  if (!activeShot.value) return;
  await act(
    async () =>
      (preview.value = await api("/shots/" + activeShot.value.id + "/preview")),
  );
}
async function exportShot() {
  if (!activeShot.value) return;
  await act(async () => {
    const pv = await api("/shots/" + activeShot.value.id + "/preview");
    preview.value = pv;
    if (pv.errors.length) throw new Error(pv.errors.join("；"));
    await window.studioConfirm(
      `本次预计 ${yuan(pv.estimate_cny)}。导出不会调用图片或视频生成接口；请在官网生成后登记实际消耗。`,
      "确认提交包",
    );
    const r = await api("/shots/" + activeShot.value.id + "/export", "POST", {
      confirmed: true,
      nonce: crypto.randomUUID(),
    });
    download(r.data.package_file_id);
  }, "提交包已冻结并导出，镜头等待回传");
}
function ingestCandidate(enhance = false) {
  const selectedParent = enhance ? candidate.value : null;
  if (enhance && selectedParent?.status !== "selected") {
    notify("请先选用候选", "warning");
    return;
  }
  const records = enhance
    ? gens.value.filter((x) => x.id === selectedParent.parent_id)
    : gens.value;
  if (!records.length) {
    notify("请先导出本镜提交包", "warning");
    return;
  }
  openForm(
    enhance ? "回传增强版" : "回传官网生成候选",
    [
      field("record_id", "关联冻结提交包", "select", {
        required: true,
        options: records.map((x) => ({
          value: x.id,
          label: date(x.created_at) + " · " + x.data.params.model,
        })),
      }),
      field("file", "视频文件", "file", {
        required: true,
        accept: "video/mp4,video/quicktime",
        wide: true,
      }),
      field("label", "候选名称", "text"),
      field("credits", "实际消耗积分", "number", { min: 0 }),
      field("amount_cny", "实际人民币（可空，按积分换算）", "number", {
        min: 0,
      }),
      field("task_url", "官网任务链接（可选）", "url"),
    ],
    { record_id: records[0].id, credits: 0, amount_cny: "" },
    async (v) => {
      const f = await upload(v.file);
      const r = await api(
        "/generations/" + v.record_id + "/candidates",
        "POST",
        {
          ...v,
          file: undefined,
          file_id: f.id,
          enhanced_parent_id: selectedParent?.id,
          amount_cny: v.amount_cny === "" ? null : Number(v.amount_cny),
        },
      );
      candidateId.value = r.id;
      nav("review");
      shotId.value = r.shot_id;
    },
    "视频在后台检测元数据并每 0.5 秒抽帧，原始文件按内容哈希去重。",
  );
}
async function review(verdict) {
  if (!candidate.value) return;
  await act(
    () =>
      api("/candidates/" + candidate.value.id + "/review", "POST", {
        verdict,
        checks: reviewChecks.value,
        issues: issue.value
          ? [{ time_s: Number(issueTime.value), note: issue.value }]
          : [],
        in_point: Number(issueTime.value) || 0,
      }),
    "审片记录已保存",
  );
}
async function frameStep(delta) {
  const v = videoPlayer.value;
  if (v)
    v.currentTime = Math.max(
      0,
      Math.min(
        v.duration || 0,
        v.currentTime + delta / (candidate.value?.data.media_meta?.fps || 30),
      ),
    );
}
async function copy(text) {
  try {
    await navigator.clipboard.writeText(text || "");
    notify("已复制");
  } catch {
    notify("复制失败，请选中文字手动复制", "error");
  }
}
async function enhancementExport() {
  await act(async () => {
    const data = await api(
      "/candidates/" + candidate.value.id + "/enhancement",
    );
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "增强参数.json";
    a.click();
    URL.revokeObjectURL(a.href);
  });
}
function placementForm() {
  openForm(
    "替换指定镜头的商品道具",
    [
      field("shot_id", "目标镜头", "select", {
        required: true,
        options: shotList.value.map((x) => ({ value: x.id, label: x.name })),
      }),
      field("asset_version_id", "已定稿商品", "select", {
        required: true,
        options: finalizedVersions.value
          .filter((x) => byId("asset", x.parent_id)?.data.type === "PROD")
          .map((x) => ({ value: x.id, label: versionLabel(x) })),
      }),
      field("exposure", "露出方式", "text"),
      field("keep_features", "必须保留的特征", "textarea"),
      field("checks", "植入检查", "checks", {
        wide: true,
        options: [
          { value: "package", label: "包装与参考一致" },
          { value: "pattern", label: "图案文字不变形" },
          { value: "contact", label: "接触与比例自然" },
          { value: "identity", label: "未遮挡角色动作" },
        ],
      }),
    ],
    { shot_id: activeShot.value?.id },
    (v) =>
      api("/projects/" + projectId.value + "/placement", "POST", {
        ...v,
        checks: {
          package: v.package,
          pattern: v.pattern,
          contact: v.contact,
          identity: v.identity,
        },
      }),
    "只替换目标镜头，原候选保留为历史，该镜头需重新导出与审片。",
  );
}
async function saveEdit() {
  await act(
    () =>
      save(
        "project",
        {
          data: {
            ...project.value.data,
            srt: srt.value,
            edit_notes: editNotes.value,
          },
        },
        projectId.value,
      ),
    "字幕与剪辑说明已保存",
  );
}
async function exportEdit() {
  await act(async () => {
    await saveEdit();
    const r = await api(
      "/projects/" + projectId.value + "/edit-package",
      "POST",
      { srt: srt.value },
    );
    download(r.data.file_id);
  }, "剪映素材包已导出");
}
const playlist = computed(() =>
  shotList.value
    .map((sh) => {
      const c = selected(sh.id);
      if (!c) return null;
      return (
        list("candidate")
          .filter((x) => x.data.enhanced_parent_id === c.id && x.data.approved)
          .at(-1) || c
      );
    })
    .filter(Boolean),
);
function ingestFinal() {
  const eps = own("edit_package");
  if (!eps.length) {
    notify("请先导出剪映素材包", "warning");
    return;
  }
  openForm(
    "上传剪映成片",
    [
      field("file", "MP4 成片", "file", {
        required: true,
        accept: "video/mp4",
        wide: true,
      }),
      field("edit_package_id", "对应剪辑素材包版本", "select", {
        required: true,
        options: eps.map((x) => ({
          value: x.id,
          label: "v" + x.version + " · " + date(x.created_at),
        })),
      }),
      field("edit_version", "剪辑版本", "text", { required: true }),
      field("platform_variant", "平台版本", "select", {
        required: true,
        options: ["主版", "抖音", "小红书", "视频号", "YouTube", "TikTok"],
      }),
    ],
    {
      edit_package_id: eps.at(-1).id,
      edit_version: "v" + (finals.value.length + 1),
      platform_variant: "主版",
    },
    async (v) => {
      const f = await upload(v.file);
      const fc = await api("/projects/" + projectId.value + "/finals", "POST", {
        file_id: f.id,
        edit_package_id: v.edit_package_id,
        edit_version: v.edit_version,
        platform_variant: v.platform_variant,
      });
      finalId.value = fc.id;
      nav("delivery");
    },
    "自动检测画幅、分辨率、时长、音轨、黑帧、静音段和 SRT，完成后仍需人工完整观看与试听。",
  );
}
async function confirmFinal() {
  await act(
    () =>
      api("/finals/" + activeFinal.value.id + "/confirm", "POST", {
        checks: finalChecks.value,
      }),
    "成片已标记为可发布",
  );
}
async function archiveFinal() {
  await act(async () => {
    const r = await api(
      "/projects/" + projectId.value + "/archive/" + activeFinal.value.id,
      "POST",
    );
    download(r.data.file_id);
  }, "交付归档已打包");
}
function releaseForm() {
  openForm(
    "登记手动发布记录",
    [
      field("final_id", "对应成片", "select", {
        required: true,
        options: finals.value
          .filter((x) => x.status === "publishable")
          .map((x) => ({
            value: x.id,
            label: x.data.edit_version + " · " + x.name,
          })),
      }),
      field("platform", "发布平台", "select", {
        required: true,
        options: ["抖音", "小红书", "视频号", "YouTube", "TikTok", "其他"],
      }),
      field("url", "发布链接", "url", { required: true, wide: true }),
      field("published_at", "发布时间", "datetime-local", { required: true }),
    ],
    { platform: "抖音", published_at: new Date().toISOString().slice(0, 16) },
    (v) =>
      save("release", {
        project_id: projectId.value,
        parent_id: v.final_id,
        name: v.platform,
        data: v,
      }),
  );
}
function csvForm() {
  openForm(
    "上传平台指标 CSV",
    [
      field("file", "CSV 文件（UTF-8 / GBK）", "file", {
        required: true,
        accept: ".csv",
        wide: true,
      }),
    ],
    {},
    async (v) => {
      const f = await upload(v.file);
      csvFileId.value = f.id;
      csvData.value = await api("/csv/" + f.id + "/preview");
      csvMapping.value = clone(
        list("csv_mapping").find((x) => x.name === activeRelease.value?.name)
          ?.data.mapping || {},
      );
      csvRelease.value = activeRelease.value?.id || "";
    },
  );
}
async function commitCSV() {
  await act(
    () =>
      api("/projects/" + projectId.value + "/metrics", "POST", {
        file_id: csvFileId.value,
        release_id: csvRelease.value,
        mapping: csvMapping.value,
        row_index: Number(csvRow.value),
        period: csvPeriod.value,
        save_mapping: true,
        platform: activeRelease.value?.name,
      }),
    "CSV 已导入，相同文件与映射不会重复累计",
  );
  csvData.value = null;
}
function retentionForm() {
  if (!metrics.value) {
    notify("请先导入指标 CSV", "warning");
    return;
  }
  openForm(
    "手录留存采样点",
    [
      field("second", "视频时间（秒）", "number", { required: true, min: 0 }),
      field("ratio", "留存比例（0–1）", "number", {
        required: true,
        min: 0,
        max: 1,
      }),
    ],
    { second: 0, ratio: 1 },
    (v) =>
      save("retention_point", {
        project_id: projectId.value,
        parent_id: metrics.value.id,
        name: v.second + "s",
        data: { second: Number(v.second), ratio: Number(v.ratio) },
      }),
  );
}
async function saveRetro() {
  const r = own("retro").at(-1);
  return act(
    () =>
      save(
        "retro",
        {
          project_id: projectId.value,
          parent_id: activeRelease.value?.id || null,
          name: "复盘与下一条实验",
          status: retroForm.value.status,
          data: clone(retroForm.value),
        },
        r?.id,
      ),
    "复盘已保存",
  );
}
async function nextProject() {
  const r = await saveRetro();
  if (!r) return;
  await act(async () => {
    const next = await api("/projects/" + projectId.value + "/next", "POST", {
      retro_id: r.id,
    });
    await refresh();
    nav("brief", next.id);
    syncForms();
  }, "已创建下一条简报草稿，尚未开始生成");
}
function costForm(obj) {
  openForm(
    "登记费用流水",
    [
      field("category", "费用类别", "select", {
        required: true,
        options: ["视频生成", "图片生成", "增强", "LLM", "其他"],
      }),
      field("amount_cny", "人民币金额", "number", { required: true, min: 0 }),
      field("credits", "积分", "number", { min: 0 }),
      field("note", "账单核对说明", "textarea", { wide: true }),
    ],
    {
      category: obj?.name || "其他",
      amount_cny: obj ? obj.amount_fen / 100 : 0,
      credits: obj?.data.credits || 0,
      note: obj?.data.note || "",
    },
    (v) =>
      save(
        "cost_entry",
        {
          project_id: obj?.project_id || projectId.value || null,
          name: v.category,
          amount_cny: v.amount_cny,
          data: {
            ...(obj?.data || {}),
            credits: v.credits,
            note: v.note,
            unpriced: false,
            estimated: false,
          },
        },
        obj?.id,
      ),
  );
}
async function saveLLM(which) {
  const form = which === "llm_text" ? llmText.value : llmVision.value;
  await act(
    () => api("/settings/" + which, "POST", form),
    "LLM 配置已保存；密钥不会返回浏览器",
  );
  form.api_key = "";
}
function templateForm(t) {
  openForm(
    "编辑提示词模板 · " + t.data.label,
    [
      field("body", "Jinja2 模板正文", "textarea", {
        required: true,
        wide: true,
        rows: 14,
        help: "使用 {{ context }} 接收上下文；保存生成新版本，保留历史。",
      }),
    ],
    t.data,
    (v) => save("prompt_template", { data: { ...t.data, body: v.body } }, t.id),
  );
}
async function makeBackup() {
  await act(async () => {
    const t = await api("/backup", "POST");
    await waitTask(t.id);
    const d = byId("task", t.id);
    if (d?.data.file_id) download(d.data.file_id);
  }, "备份已创建，API 主密钥保留在系统凭据管理器中");
}
function restoreForm() {
  openForm(
    "从备份恢复",
    [
      field("file", "猫片工场备份 ZIP", "file", {
        required: true,
        accept: ".zip",
        wide: true,
      }),
      field("confirmed", "我已确认用备份替换当前数据", "checkbox", {
        required: true,
      }),
    ],
    {},
    async (v) => {
      if (!v.confirmed) throw new Error("请先勾选恢复确认");
      const f = await upload(v.file);
      await api("/restore", "POST", { file_id: f.id, confirmed: true });
      await refresh();
      syncForms();
    },
    "恢复前系统自动保留当前数据备份。请等待所有后台检测完成后操作。",
  );
}
async function waitTask(id) {
  for (let i = 0; i < 180; i++) {
    await new Promise((r) => setTimeout(r, 800));
    await refresh();
    const t = byId("task", id);
    if (t?.status === "failed") throw new Error(t.data.error);
    if (t?.status === "success") return t;
  }
  throw new Error("后台仍在处理，可稍后查看结果");
}
async function askAI(purpose, context = {}, imageFileId) {
  try {
    await window.studioConfirm(
      "将向你配置的大模型发送本项目上下文" +
        (imageFileId ? "和这张截图" : "") +
        "，可能产生 API 费用。结果作为 AI 建议，需你确认后采用。",
      "调用文本 AI",
    );
    await act(async () => {
      const t = await api("/llm", "POST", {
        project_id: projectId.value,
        purpose,
        context,
        image_file_id: imageFileId,
        confirmed: true,
      });
      notify("AI 正在处理，可继续操作其他页面");
      const done = await waitTask(t.id);
      aiResult.value = { purpose, context, ...done.data.result };
      showAI.value = true;
    });
  } catch {}
}
async function adoptAI() {
  if (!aiResult.value) return;
  await act(async () => {
    const a = aiResult.value,
      r = JSON.parse(aiDraft.value);
    if (a.purpose === "directions") {
      for (const d of r.directions)
        await save("story_direction", {
          project_id: projectId.value,
          name: d.title,
          data: { ...d, origin: "AI 建议", is_selected: false },
        });
    } else if (a.purpose === "script")
      await save("script", {
        project_id: projectId.value,
        name: "AI 剧情草稿",
        data: r,
      });
    else if (a.purpose === "storyboard") {
      for (const sh of r.shots) {
        const sr = await save("shot", {
          project_id: projectId.value,
          parent_id: currentScript.value?.id,
          name: sh.title,
          seq: shotList.value.length,
          duration_s: sh.duration_s,
          data: { ...sh, checks: {} },
        });
        for (const [i, slot] of ["主体", "场景", "道具"].entries())
          await save("shot_binding", {
            project_id: projectId.value,
            shot_id: sr.id,
            name: slot,
            seq: i,
            data: {
              slot,
              required: true,
              asset_version_id: null,
              with_accessories: slot === "主体",
            },
          });
        await refresh();
      }
    } else if (a.purpose === "screenshot") {
      for (const c of r.comments || [])
        await save("evidence", {
          project_id: projectId.value,
          parent_id: a.context.reference_id,
          name: c.text.slice(0, 20),
          data: { text: c.text, likes: c.likes, source: "识别" },
        });
    } else if (a.purpose === "comment_tags") {
      for (const tag of r.comments) {
        const e = byId("evidence", tag.id);
        if (e)
          await save(
            "evidence",
            { data: { ...e.data, tags: tag.tags || [] } },
            e.id,
          );
      }
    } else if (a.purpose === "retro")
      retroForm.value = { ...retroForm.value, ...r };
    else if (
      ["portrait", "scene", "prop"].includes(a.purpose) &&
      activeAsset.value
    ) {
      await save(
        "asset",
        { data: { ...activeAsset.value.data, prompt: r.prompt } },
        activeAsset.value.id,
      );
    } else if (a.purpose === "video_prompt" && activeShot.value)
      await save(
        "shot",
        { data: { ...activeShot.value.data, prompt: r.prompt } },
        activeShot.value.id,
      );
    showAI.value = false;
  }, "AI 建议已保存为可编辑草稿");
}
function help() {
  openForm(
    "使用帮助",
    [field("guide", "生产流程", "textarea", { wide: true, rows: 13 })],
    {
      guide:
        "01 填写目标人群并确认简报。\n02 导入链接、截图或评论，选定有依据的故事方向。\n03 编写或用已配置 LLM 生成剧情、分镜与提示词，完成每镜检查。\n04 回传官网生成的图片/声音，登记来源与定稿，满足资产需求。\n05 核对模型档案、绑定定稿版本、导出提交包，在官网手动生成，再回传审片。\n06 导出剪映素材包，在剪映完成剪辑配音字幕，回传 MP4 并通过质检。\n07 手动发布、导入 CSV，保存单变量实验并创建下一条简报。\n\n所有文件和数据保存在本机。LLM 可选，未配置时仍可手工跑完整个流程。",
    },
    async () => {},
  );
}

function regenerateSrt() {
  const time = (t) => {
    let n = Math.round(t * 1000);
    return (
      String(Math.floor(n / 3600000)).padStart(2, "0") +
      ":" +
      String(Math.floor(n / 60000) % 60).padStart(2, "0") +
      ":" +
      String(Math.floor(n / 1000) % 60).padStart(2, "0") +
      "," +
      String(n % 1000).padStart(3, "0")
    );
  };
  srt.value =
    shotList.value
      .filter((x) => x.data.line_text)
      .map(
        (x, i) =>
          `${i + 1}\n${time(x.start)} --> ${time(x.end)}\n${x.data.line_text}`,
      )
      .join("\n\n") + "\n";
}
function importComments() {
  openForm(
    "导入评论 CSV",
    [
      field("file", "评论 CSV 文件", "file", {
        required: true,
        accept: ".csv",
        wide: true,
      }),
    ],
    {},
    async (v) => {
      const f = await upload(v.file);
      const data = await api("/csv/" + f.id + "/preview");
      commentImport.value = f.id;
      commentColumns.value = data.columns;
      commentTextColumn.value = data.columns[0] || "";
      commentLikesColumn.value = "";
    },
  );
}
async function commitComments() {
  await act(
    () =>
      api("/projects/" + projectId.value + "/comments-csv", "POST", {
        file_id: commentImport.value,
        text_column: commentTextColumn.value,
        likes_column: commentLikesColumn.value,
      }),
    "评论已导入，仅保存文字和点赞数",
  );
  commentImport.value = null;
}
async function addAudioBinding() {
  if (!activeShot.value) return;
  await act(
    () =>
      save("shot_binding", {
        project_id: projectId.value,
        shot_id: activeShot.value.id,
        parent_id: activeShot.value.id,
        name: "声音",
        seq: binds.value.length,
        data: { slot: "声音", required: false, asset_version_id: null },
      }),
    "已增加可选声音参考",
  );
}

onMounted(async () => {
  await ff();
  syncForms();
  if (["edit", "delivery"].includes(page.value) && project.value) {
    const draft = await api("/projects/" + projectId.value + "/srt");
    srt.value = draft.srt;
  }
  llmText.value = clone(
    db.settings.llm_text || {
      provider: "openai",
      base_url: "https://api.openai.com/v1",
      model: "",
    },
  );
  llmVision.value = clone(
    db.settings.llm_vision || {
      provider: "openai",
      base_url: "https://api.openai.com/v1",
      model: "",
    },
  );
  budget.value = clone(db.settings.budget || budget.value);
  timer = setInterval(refresh, 3500);
});
onBeforeUnmount(() => {
  clearInterval(timer);
  clearTimeout(autoTimer);
});
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#dashboard" @click="nav('dashboard')"
        ><div class="brand-mark"><PawPrint :size="31" /></div>
        <span>猫片工场<small>PET VIDEO STUDIO</small></span></a
      >
      <div class="workspace-label">创作空间 <span>LOCAL</span></div>
      <nav class="main-nav">
        <button
          :class="{ active: page === 'dashboard' }"
          @click="nav('dashboard')"
        >
          <LayoutDashboard />工作台</button
        ><button
          :class="{
            active: ['projects', 'brief', 'research', 'script'].includes(page),
          }"
          @click="nav('projects')"
        >
          <FolderOpen />视频项目
          <span class="nav-count">{{ list("project").length }}</span></button
        ><button
          :class="{ active: ['assets', 'library'].includes(page) }"
          @click="nav(project ? 'assets' : 'library')"
        >
          <Images />数字资产</button
        ><button
          :class="{
            active: [
              'models',
              'bindings',
              'review',
              'progress',
              'placement',
            ].includes(page),
          }"
          @click="nav('progress')"
        >
          <Clapperboard />镜头进度
          <i v-if="pending.length">{{ pending.length }}</i></button
        ><button
          :class="{ active: ['edit', 'delivery'].includes(page) }"
          @click="nav('delivery')"
        >
          <Video />成片与交付</button
        ><button :class="{ active: page === 'retro' }" @click="nav('retro')">
          <ChartNoAxesCombined />数据复盘
        </button>
      </nav>
      <div class="sidebar-note">
        <span class="live-dot" /> 本机私有工作台
        <p>官网生成 · 本地管理<br />每一次创作都有迹可循</p>
      </div>
      <nav class="bottom-nav">
        <button
          :class="{ active: page === 'settings' }"
          @click="nav('settings')"
        >
          <Settings2 />模型档案与设置</button
        ><button :class="{ active: page === 'costs' }" @click="nav('costs')">
          <Wallet />预算与费用</button
        ><button @click="help"><HelpCircle />使用帮助</button>
      </nav>
      <div class="profile">
        <div class="avatar"><PawPrint :size="19" /></div>
        <div>我的工作室<small>个人本地版 · v1.0</small></div>
        <ShieldCheck :size="18" />
      </div>
    </aside>
    <div class="main-shell">
      <header class="topbar">
        <div class="breadcrumbs">
          <LayoutDashboard :size="16" /><ChevronRight :size="14" /><span>{{
            projectRequired && project ? project.name : "创作工作台"
          }}</span
          ><ChevronRight :size="14" /><b>{{ titles[page] || "工作台" }}</b>
        </div>
        <div class="top-actions">
          <div class="search-input">
            <Search :size="16" /><input
              v-model="search"
              placeholder="搜索当前列表…"
              aria-label="搜索当前列表"
            />
          </div>
          <button class="icon-btn" @click="help" aria-label="帮助">
            <HelpCircle :size="20" /></button
          ><span class="local-pill"
            ><span class="live-dot" /> 本地半手动模式</span
          >
        </div>
      </header>
      <div v-if="connectionError" class="offline" role="alert">
        {{ connectionError }} <button @click="refresh">重新连接</button>
      </div>
      <main>
        <div class="page-heading">
          <div>
            <div class="eyebrow">
              {{
                ["settings", "costs"].includes(page)
                  ? "WORKSPACE SETTINGS"
                  : "CREATE SOMETHING THAT RESONATES"
              }}
            </div>
            <h1>{{ titles[page] || "项目工作台" }}</h1>
            <p>{{ subtitles[page] }}</p>
          </div>
          <div class="heading-actions">
            <select
              v-if="projectRequired && list('project').length"
              :value="projectId"
              @change="nav(page, $event.target.value)"
              aria-label="当前项目"
            >
              <option v-for="p in list('project')" :value="p.id" :key="p.id">
                {{ p.name }}
              </option></select
            ><button
              v-if="['dashboard', 'projects'].includes(page)"
              class="accent"
              @click="newProject"
            >
              <Plus :size="18" />新建视频项目</button
            ><button
              v-if="['assets', 'library'].includes(page)"
              class="accent"
              @click="assetForm"
            >
              <Plus :size="18" />新建数字资产</button
            ><button v-if="page === 'settings'" @click="makeBackup">
              <Download :size="17" />备份数据
            </button>
          </div>
        </div>

        <section v-if="projectRequired && !project" class="empty large">
          <div class="empty-icon"><FolderOpen :size="38" /></div>
          <h2>先为下一条故事创建项目</h2>
          <p>确定目标人群，整理真实共鸣，再开始猫咪的表演。</p>
          <button class="accent" @click="newProject">
            <Plus :size="18" />新建视频项目
          </button>
        </section>
        <template v-else>
          <div v-if="projectRequired" class="project-stages">
            <button
              v-for="(name, i) in stages"
              :key="name"
              :class="{
                current:
                  page === stagePages[i] ||
                  (i === 4 && subpages.models.includes(page)) ||
                  (i === 5 && subpages.edit.includes(page)),
                done: project.data.completed_stages?.includes(i + 1),
              }"
              @click="nav(stagePages[i])"
            >
              <span
                ><Check
                  v-if="project.data.completed_stages?.includes(i + 1)"
                  :size="13"
                /><template v-else>{{
                  String(i + 1).padStart(2, "0")
                }}</template></span
              >{{ name }}<ChevronRight v-if="i < 6" :size="13" />
            </button>
          </div>
          <div v-if="subpages.models.includes(page)" class="section-tabs">
            <button
              v-for="p in [
                'models',
                'bindings',
                'review',
                'progress',
                'placement',
              ]"
              :key="p"
              :class="{ active: page === p }"
              @click="nav(p)"
            >
              {{
                {
                  models: "选择模型",
                  bindings: "绑定素材",
                  review: "提交与审片",
                  progress: "镜头进度",
                  placement: "商品植入 · 可选",
                }[p]
              }}</button
            ><span class="muted push-right"
              >{{ shotList.length }} 镜 ·
              {{ shotList.reduce((s, x) => s + x.duration_s, 0) }}s ·
              {{ activeBrief?.data.aspect_ratio }}</span
            >
          </div>
          <div v-if="subpages.edit.includes(page)" class="section-tabs">
            <button :class="{ active: page === 'edit' }" @click="nav('edit')">
              剪辑准备</button
            ><button
              :class="{ active: page === 'delivery' }"
              @click="nav('delivery')"
            >
              成片检查与归档</button
            ><span class="muted push-right">剪辑与配音在剪映内完成</span>
          </div>

          <template v-if="page === 'dashboard'">
            <div class="dashboard-grid">
              <div class="dashboard-left">
                <div class="stats-row">
                  <div
                    class="stat"
                    v-for="(n, i) in [
                      list('project').filter((x) => x.status !== 'complete')
                        .length,
                      list('project').filter((x) => x.data.stage < 7).length,
                      pending.length,
                      monthlySpend,
                    ]"
                    :key="i"
                  >
                    <span class="stat-icon" :class="{ amber: i % 2 }"
                      ><component
                        :is="[FolderOpen, ShieldCheck, Clapperboard, Wallet][i]"
                        :size="22"
                    /></span>
                    <div>
                      <p>
                        {{
                          [
                            "进行中项目",
                            "待确认项目",
                            "待回传镜头",
                            "本月已记花费",
                          ][i]
                        }}
                      </p>
                      <strong>{{ i === 3 ? yuan(n) : n }}</strong>
                    </div>
                  </div>
                </div>
                <section class="welcome-card">
                  <div class="welcome-art">
                    <svg
                      viewBox="0 0 260 240"
                      aria-label="猫咪创作插画"
                      role="img"
                    >
                      <circle cx="130" cy="115" r="98" fill="#e8eee4" />
                      <path d="M40 208h185" stroke="#b6c4b5" stroke-width="2" />
                      <path
                        d="M77 121 Q63 70 74 44 L112 71 Q140 61 162 72 L192 44 Q205 88 188 121"
                        fill="#d6a16c"
                      />
                      <ellipse
                        cx="133"
                        cy="125"
                        rx="63"
                        ry="62"
                        fill="#e5b784"
                      />
                      <path
                        d="M90 115 Q110 88 130 128 Q153 86 179 118 Q188 163 134 179 Q79 161 90 115"
                        fill="#f9ecda"
                      />
                      <path
                        d="M90 102l13 6M169 104l-13 5M125 71l6 18M145 71l-5 18"
                        stroke="#ad754b"
                        stroke-width="6"
                        stroke-linecap="round"
                      />
                      <ellipse cx="109" cy="124" rx="7" ry="9" fill="#345144" />
                      <ellipse cx="157" cy="124" rx="7" ry="9" fill="#345144" />
                      <path d="M126 145q7-7 14 0l-7 6z" fill="#cd8a78" />
                      <path
                        d="M132 152q-9 10-18 0m19 0q9 10 18 0"
                        fill="none"
                        stroke="#876c59"
                        stroke-width="2"
                      />
                      <path
                        d="M99 175Q82 184 84 209h99q0-29-22-34"
                        fill="#d7a372"
                      />
                      <path
                        d="M110 178l24 20 24-20"
                        stroke="#597e65"
                        stroke-width="5"
                        fill="none"
                      />
                      <path d="M198 195h30v-25h-30z" fill="#8fa78e" />
                      <path
                        d="M206 167q-7-8 1-14m9 14q-7-8 1-14"
                        fill="none"
                        stroke="#8fa78e"
                        stroke-width="2"
                      /></svg
                    ><small>让猫咪，演出生活的小情绪。</small>
                  </div>
                  <div class="welcome-copy">
                    <span class="pill">{{
                      projects.length ? "继续你的创作" : "YOUR NEXT CAT STORY"
                    }}</span>
                    <h2>
                      {{
                        projects.length
                          ? projects[0].name
                          : "一个真实共鸣，一条猫咪故事。"
                      }}
                    </h2>
                    <p>
                      {{
                        projects.length
                          ? "每一步有记录，每个版本可追溯。继续完成当前阶段。"
                          : "从人群简报开始，把想说的话，变成观众看得懂、听得清的猫咪剧情。"
                      }}
                    </p>
                    <div class="mini-steps">
                      <span
                        v-for="(s, i) in [
                          '简报',
                          '选题',
                          '分镜',
                          '资产',
                          '成片',
                        ]"
                        :key="s"
                        ><i
                          :class="{
                            done: projects[0]?.data.completed_stages?.includes(
                              i + 1,
                            ),
                          }"
                          >{{ i + 1 }}</i
                        >{{ s }}</span
                      >
                    </div>
                    <button
                      class="primary"
                      @click="
                        projects.length
                          ? nav(
                              stagePages[(projects[0].data.stage || 1) - 1],
                              projects[0].id,
                            )
                          : newProject()
                      "
                    >
                      {{ projects.length ? "继续制作" : "创建第一个项目"
                      }}<ArrowRight :size="16" />
                    </button>
                  </div>
                </section>
                <section class="panel">
                  <div class="panel-title">
                    <h2>
                      最近项目 <small>{{ list("project").length }}</small>
                    </h2>
                    <div class="segmented">
                      <button
                        v-for="(s, k) in {
                          all: '全部',
                          active: '制作中',
                          complete: '已完成',
                        }"
                        :class="{ active: filter === k }"
                        :key="k"
                        @click="filter = k"
                      >
                        {{ s }}
                      </button>
                    </div>
                    <button
                      class="text-btn push-right"
                      @click="nav('projects')"
                    >
                      全部项目<ChevronRight :size="14" />
                    </button>
                  </div>
                  <div v-if="!projects.length" class="empty">
                    <FolderOpen :size="30" />
                    <p>还没有项目，先创建一份简报。</p>
                  </div>
                  <div v-else class="project-grid">
                    <article
                      v-for="p in projects.slice(0, 6)"
                      :key="p.id"
                      class="project-card"
                      @click="nav(stagePages[(p.data.stage || 1) - 1], p.id)"
                    >
                      <div class="project-cover">
                        <img
                          v-if="
                            list('asset').find(
                              (a) => a.project_id === p.id && cover(a),
                            )
                          "
                          :src="
                            fileUrl(
                              cover(
                                list('asset').find(
                                  (a) => a.project_id === p.id && cover(a),
                                ),
                              ),
                            )
                          "
                          alt="项目角色"
                        /><PawPrint v-else :size="48" /><span class="pill">{{
                          label(p.status)
                        }}</span>
                      </div>
                      <div class="project-card-body">
                        <h3>{{ p.name }}</h3>
                        <p>
                          {{
                            list("brief", p.id)[0]?.data.audience ||
                            "待填写人群"
                          }}
                          · {{ list("shot", p.id).length }} 镜
                        </p>
                        <div class="progress-track">
                          <div
                            :style="{
                              width:
                                ((p.data.completed_stages?.length || 0) / 7) *
                                  100 +
                                '%',
                            }"
                          />
                        </div>
                        <footer>
                          <span>{{ stages[(p.data.stage || 1) - 1] }}</span
                          ><b>继续制作 <ChevronRight :size="13" /></b>
                        </footer>
                      </div>
                    </article>
                  </div>
                </section>
              </div>
              <aside class="dashboard-right">
                <section class="panel">
                  <div class="panel-title">
                    <h2>待回传镜头</h2>
                    <span class="pill amber">{{ pending.length }} 项</span>
                  </div>
                  <div v-if="!pending.length" class="empty small">
                    <CheckCheck :size="26" />
                    <p>所有导出均已登记回传<br />新的提交包会出现在这里</p>
                  </div>
                  <button
                    v-for="r in pending.slice(0, 5)"
                    class="pending-row"
                    :key="r.id"
                    @click="
                      nav('review', r.project_id);
                      shotId = r.shot_id;
                    "
                  >
                    <Clapperboard :size="19" /><span
                      ><b>{{ r.name }}</b
                      ><small>{{ date(r.created_at) }}</small></span
                    ><span class="status awaiting">待回传</span>
                  </button>
                </section>
                <section class="panel">
                  <div class="panel-title">
                    <h2>本月预算</h2>
                    <button class="text-btn push-right" @click="nav('costs')">
                      <Settings2 :size="15" />
                    </button>
                  </div>
                  <div class="budget-amounts">
                    <div>
                      <small>预算上限</small
                      ><strong>{{
                        yuan(db.settings.budget?.monthly_cap ?? 500)
                      }}</strong>
                    </div>
                    <div>
                      <small>已记花费</small
                      ><strong>{{ yuan(monthlySpend) }}</strong>
                    </div>
                  </div>
                  <div class="progress-track">
                    <div
                      :style="{
                        width:
                          Math.min(
                            100,
                            (monthlySpend /
                              (db.settings.budget?.monthly_cap || 500)) *
                              100,
                          ) + '%',
                      }"
                    />
                  </div>
                  <p class="note">达到上限后暂停导出新提交包。</p>
                </section>
                <section class="panel">
                  <div class="panel-title">
                    <h2>模型档案</h2>
                    <button
                      class="text-btn push-right"
                      @click="nav('settings')"
                    >
                      管理<ChevronRight :size="14" />
                    </button>
                  </div>
                  <div v-for="m in activeModels" :key="m.id" class="model-mini">
                    <Layers :size="17" /><b>{{ m.name }}</b
                    ><span
                      class="pill"
                      :class="{ amber: !m.data.verified_at }"
                      >{{ m.data.verified_at || "未核对" }}</span
                    >
                  </div>
                  <p class="note">官网生成前，请核对当前能力与价格。</p>
                </section>
              </aside>
            </div>
            <div class="workflow-strip">
              <b>制作流程</b
              ><button
                v-for="(s, i) in stages"
                :key="s"
                @click="nav(stagePages[i])"
              >
                {{ s }}<ArrowRight v-if="i < 6" :size="13" />
              </button>
            </div>
          </template>

          <template v-if="page === 'projects'"
            ><section class="panel">
              <div class="panel-title">
                <h2>全部视频项目</h2>
                <div class="segmented">
                  <button
                    v-for="(s, k) in {
                      all: '全部',
                      active: '制作中',
                      draft: '草稿',
                      complete: '已完成',
                    }"
                    :key="k"
                    :class="{ active: filter === k }"
                    @click="filter = k"
                  >
                    {{ s }}
                  </button>
                </div>
              </div>
              <div v-if="!projects.length" class="empty large">
                <FolderOpen :size="42" />
                <h3>还没有符合条件的项目</h3>
                <button class="primary" @click="newProject">新建项目</button>
              </div>
              <div v-else class="project-list">
                <div v-for="p in projects" :key="p.id" class="project-list-row">
                  <div class="project-list-icon">
                    <Clapperboard :size="26" />
                  </div>
                  <div>
                    <h3>{{ p.name }}</h3>
                    <p class="muted">
                      {{
                        list("brief", p.id)[0]?.data.audience || "人群待填写"
                      }}
                    </p>
                  </div>
                  <span class="pill">{{ stages[(p.data.stage || 1) - 1] }}</span
                  ><span>{{ yuan(spent(p.id)) }}</span
                  ><small>{{ date(p.updated_at) }}</small
                  ><button
                    class="primary"
                    @click="nav(stagePages[(p.data.stage || 1) - 1], p.id)"
                  >
                    继续制作<ArrowRight :size="15" /></button
                  ><button
                    class="icon-btn"
                    @click="remove('project', p.id)"
                    aria-label="归档项目"
                  >
                    <Trash2 :size="16" />
                  </button>
                </div>
              </div></section
          ></template>

          <template v-if="page === 'brief' && project"
            ><div class="two-col">
              <section class="panel">
                <div class="panel-title">
                  <h2><span class="num">1</span>项目与目标人群</h2>
                  <span class="muted push-right">{{
                    saving || "草稿自动保存"
                  }}</span>
                </div>
                <div class="form-grid">
                  <label class="field full"
                    ><span>人群标签（可自定义，以顿号分隔）</span
                    ><input
                      v-model="tagsText"
                      placeholder="上班族、都市生活、轻松共鸣" /></label
                  ><label class="field full"
                    ><span>项目名称</span
                    ><input
                      :value="project.name"
                      @change="
                        act(
                          () =>
                            save(
                              'project',
                              { name: $event.target.value },
                              projectId,
                            ),
                          '项目名称已保存',
                        )
                      "
                      maxlength="60" /></label
                  ><label class="field full"
                    ><span
                      >目标人群 <em>*</em
                      ><small>由你主动输入，AI 不替你决定受众</small></span
                    ><textarea
                      v-model="briefForm.audience"
                      maxlength="200"
                      rows="3"
                      placeholder="例如：22—35 岁城市上班族，经常加班，喜欢真实、克制的职场日常。"
                    /><small class="align-right"
                      >{{ briefForm.audience?.length || 0 }} / 200</small
                    ></label
                  ><label class="field"
                    ><span>内容方向 <em>*</em></span
                    ><input v-model="briefForm.direction" /></label
                  ><label class="field"
                    ><span>情绪基调</span><input v-model="briefForm.emotion"
                  /></label>
                </div>
                <div class="panel-title inner">
                  <h2><span class="num">2</span>发布与成片规格</h2>
                </div>
                <div class="form-grid">
                  <div class="field full">
                    <span>发布平台 <em>*</em></span>
                    <div class="choice-row">
                      <label
                        v-for="p in [
                          '抖音',
                          '小红书',
                          '视频号',
                          'YouTube',
                          'TikTok',
                        ]"
                        :key="p"
                        ><input
                          type="checkbox"
                          :value="p"
                          v-model="briefForm.platforms"
                        />{{ p }}</label
                      >
                    </div>
                  </div>
                  <label class="field"
                    ><span>主版画幅</span
                    ><select v-model="briefForm.aspect_ratio">
                      <option>9:16</option>
                      <option>16:9</option>
                    </select></label
                  ><label class="field"
                    ><span>语言</span
                    ><input v-model="briefForm.language" /></label
                  ><label class="field"
                    ><span>最短时长（秒）</span
                    ><input
                      type="number"
                      v-model.number="briefForm.duration_min_s"
                      min="1"
                      max="600" /></label
                  ><label class="field"
                    ><span>最长时长（秒）</span
                    ><input
                      type="number"
                      v-model.number="briefForm.duration_max_s"
                      min="1"
                      max="600"
                  /></label>
                </div>
                <div class="panel-title inner">
                  <h2><span class="num">3</span>预算与创作约束</h2>
                </div>
                <div class="form-grid">
                  <label class="field"
                    ><span>项目预算上限（人民币）</span
                    ><input
                      type="number"
                      min="0"
                      step="0.01"
                      v-model.number="briefForm.budget_cap" /></label
                  ><label class="check-field"
                    ><input
                      type="checkbox"
                      v-model="briefForm.pause_on_budget"
                    />达到上限后暂停导出提交包</label
                  ><label class="check-field"
                    ><input
                      type="checkbox"
                      v-model="briefForm.placement_enabled"
                    />允许可选商品植入</label
                  ><label class="field"
                    ><span>计划产量</span
                    ><input
                      type="number"
                      min="1"
                      v-model.number="briefForm.quantity"
                  /></label>
                </div>
                <div class="hint">
                  <Info
                    :size="16"
                  />预算按实际费用流水汇总；官网花费需要回传时登记。
                </div>
              </section>
              <aside>
                <section class="panel sticky">
                  <div class="panel-title">
                    <h2>创作简报预览</h2>
                    <span class="pill push-right">实时汇总</span>
                  </div>
                  <div class="brief-preview-icon"><PawPrint :size="48" /></div>
                  <h2>{{ project.name }}</h2>
                  <dl class="definition">
                    <dt>拍给谁看</dt>
                    <dd>{{ briefForm.audience || "待填写目标人群" }}</dd>
                    <dt>内容方向</dt>
                    <dd>{{ briefForm.direction }}</dd>
                    <dt>情绪基调</dt>
                    <dd>{{ briefForm.emotion }}</dd>
                    <dt>发布平台</dt>
                    <dd>{{ briefForm.platforms?.join("、") }}</dd>
                    <dt>成片规格</dt>
                    <dd>
                      {{ briefForm.aspect_ratio }} ·
                      {{ briefForm.duration_min_s }}–{{
                        briefForm.duration_max_s
                      }}
                      秒 · {{ briefForm.language }}
                    </dd>
                    <dt>预算上限</dt>
                    <dd>{{ yuan(briefForm.budget_cap) }}</dd>
                  </dl>
                  <div class="next-note">
                    <Sparkles :size="20" />
                    <div>
                      <b>下一步，找到真实共鸣</b>
                      <p>
                        导入你收集的内容和评论，提炼猫咪能演出来的生活情境。
                      </p>
                    </div>
                  </div>
                  <p class="note">
                    {{
                      activeBrief?.data.experiment?.exp_change
                        ? "本条实验：" + activeBrief.data.experiment.exp_change
                        : "确认简报会进入素材调研，仍可返回修改。"
                    }}
                  </p>
                </section>
              </aside>
            </div>
            <div class="action-bar">
              <span
                ><ShieldCheck :size="16" />数据保存在本机 ·
                {{ saving || "自动保存草稿" }}</span
              ><button @click="saveBrief">保存草稿</button
              ><button class="accent" @click="confirmStage(1)">
                确认简报，进入素材调研<ArrowRight :size="16" />
              </button></div
          ></template>

          <template v-if="page === 'research' && project"
            ><div class="context-bar">
              <b>目标人群</b>{{ activeBrief?.data.audience
              }}<span class="push-right"
                >{{ activeBrief?.data.aspect_ratio }} ·
                {{ activeBrief?.data.duration_min_s }}–{{
                  activeBrief?.data.duration_max_s
                }}
                秒</span
              >
            </div>
            <div class="research-grid">
              <section class="panel">
                <div class="panel-title">
                  <h2>对标素材与共鸣</h2>
                  <button class="text-btn push-right" @click="referenceForm">
                    <Link :size="16" />导入链接</button
                  ><button @click="screenshotForm">
                    <ImagePlus :size="16" />上传截图</button
                  ><button @click="commentForm">
                    <MessageSquare :size="16" />手录评论
                  </button>
                </div>
                <div class="segmented">
                  <button
                    :class="{ active: filter === 'all' }"
                    @click="filter = 'all'"
                  >
                    全部素材 {{ own("reference").length }}</button
                  ><button
                    :class="{ active: filter === 'cited' }"
                    @click="filter = 'cited'"
                  >
                    已引用</button
                  ><button
                    :class="{ active: filter === 'starred' }"
                    @click="filter = 'starred'"
                  >
                    已收藏
                  </button>
                </div>
                <div class="filter-row">
                  <select v-model="sourceFilter" aria-label="素材来源筛选">
                    <option>全部平台</option>
                    <option>抖音</option>
                    <option>小红书</option>
                    <option>其他</option></select
                  ><select v-model="timeFilter" aria-label="导入时间筛选">
                    <option :value="0">全部导入时间</option>
                    <option :value="7">近 7 天导入</option>
                    <option :value="30">近 30 天导入</option></select
                  ><select v-model="contentFilter" aria-label="内容类型筛选">
                    <option value="all">全部类型</option>
                    <option value="links">链接素材</option>
                    <option value="screenshots">截图素材</option>
                  </select>
                </div>
                <div v-if="!own('reference').length" class="empty">
                  <BookOpen :size="34" />
                  <h3>先放进一条真实素材</h3>
                  <p>链接、截图、手录评论都可以，保留共鸣的出处。</p>
                </div>
                <article
                  v-for="r in filteredReferences"
                  :key="r.id"
                  class="reference-card"
                >
                  <div class="reference-thumb">
                    <img
                      v-if="r.data.screenshot_file_ids?.length"
                      :src="fileUrl(r.data.screenshot_file_ids[0])"
                      alt="对标截图"
                    /><FileText v-else :size="30" />
                  </div>
                  <div class="flex-grow">
                    <span class="pill">{{
                      r.data.platform || "手动导入"
                    }}</span>
                    <h3>{{ r.name }}</h3>
                    <p class="muted">
                      {{ r.data.likes ?? "未登记" }} 赞 ·
                      {{ r.data.duration_s ?? "—" }} 秒
                    </p>
                    <a
                      v-if="r.data.url"
                      :href="r.data.url"
                      target="_blank"
                      rel="noopener noreferrer"
                      >查看原始链接<ExternalLink :size="12"
                    /></a>
                  </div>
                  <div class="column-actions">
                    <button
                      @click="
                        act(() =>
                          save(
                            'reference',
                            { data: { ...r.data, is_cited: !r.data.is_cited } },
                            r.id,
                          ),
                        )
                      "
                    >
                      {{ r.data.is_cited ? "✓ 已引用" : "引用" }}</button
                    ><button
                      @click="
                        act(() =>
                          save(
                            'reference',
                            {
                              data: {
                                ...r.data,
                                is_starred: !r.data.is_starred,
                              },
                            },
                            r.id,
                          ),
                        )
                      "
                    >
                      {{ r.data.is_starred ? "已收藏" : "收藏" }}</button
                    ><button
                      class="text-btn danger"
                      @click="remove('reference', r.id)"
                    >
                      归档
                    </button>
                  </div>
                </article>
                <div class="panel-title inner">
                  <h2>共鸣证据</h2>
                  <span class="muted">仅存评论文字与点赞数</span>
                </div>
                <blockquote v-for="e in own('evidence')" :key="e.id">
                  <MessageSquare :size="18" />
                  <div>
                    {{ e.data.text
                    }}<small
                      >{{ e.data.likes || 0 }} 赞 ·
                      {{
                        byId("reference", e.parent_id)?.name || "手录评论"
                      }}</small
                    >
                  </div>
                  <button
                    class="icon-btn push-right"
                    @click="remove('evidence', e.id)"
                    aria-label="归档评论"
                  >
                    <Trash2 :size="13" />
                  </button>
                </blockquote>
                <p v-if="!own('evidence').length" class="note">
                  还没有登记评论，可手录或用已配置的多模态 LLM 识别截图。
                </p>
              </section>
              <aside class="panel">
                <div class="panel-title">
                  <h2>故事方向</h2>
                  <button
                    class="text-btn push-right"
                    @click="askAI('directions')"
                  >
                    <Sparkles :size="15" />AI 归纳
                  </button>
                </div>
                <button class="full-width dashed" @click="directionForm()">
                  <Plus :size="16" />新增自己的选题
                </button>
                <button class="full-width" @click="reuseTopic">
                  <BookOpen :size="15" />从选题库复用
                </button>
                <article
                  v-for="d in own('story_direction')"
                  :key="d.id"
                  class="direction-card"
                  :class="{ selected: d.data.is_selected }"
                >
                  <div>
                    <input
                      type="radio"
                      :checked="d.data.is_selected"
                      :aria-label="'选择' + d.name"
                      @change="
                        act(() =>
                          save(
                            'story_direction',
                            { data: { ...d.data, is_selected: true } },
                            d.id,
                          ),
                        )
                      "
                    />
                    <h3>{{ d.name }}</h3>
                    <span v-if="d.data.origin === 'AI 建议'" class="pill amber"
                      >AI 建议</span
                    >
                  </div>
                  <dl>
                    <dt>共鸣点</dt>
                    <dd>{{ d.data.resonance }}</dd>
                    <dt>猫咪演法</dt>
                    <dd>{{ d.data.cat_acting }}</dd>
                    <dt>情绪落点</dt>
                    <dd>{{ d.data.emotion_landing }}</dd>
                    <dt>引用依据</dt>
                    <dd>
                      {{
                        (d.data.cited_reference_ids || [])
                          .map((id) => byId("reference", id)?.name || "已归档")
                          .join("、") || "未引用素材"
                      }}
                      · {{ d.data.cited_evidence_ids?.length || 0 }} 条评论
                    </dd>
                  </dl>
                  <button class="text-btn" @click="directionForm(d)">
                    <NotebookPen :size="14" />编辑方向
                  </button>
                  <button
                    class="text-btn"
                    @click="
                      act(
                        () =>
                          save(
                            'story_direction',
                            {
                              data: {
                                ...d.data,
                                in_library: !d.data.in_library,
                              },
                            },
                            d.id,
                          ),
                        d.data.in_library ? '已移出选题库' : '已加入选题库',
                      )
                    "
                  >
                    {{ d.data.in_library ? "移出选题库" : "加入选题库" }}
                  </button>
                </article>
                <div class="hint">
                  <Info
                    :size="17"
                  />选定一个方向，且引用至少一条已登记素材或评论后，才能确认选题。
                </div>
              </aside>
            </div>
            <div class="action-bar">
              <button @click="nav('brief')">
                <ArrowLeft :size="16" />人群简报</button
              ><span class="push-right"
                >已选择
                {{
                  own("story_direction").filter((x) => x.data.is_selected)
                    .length
                }}
                个故事方向</span
              ><button class="accent" @click="confirmStage(2)">
                确认选题，进入剧本分镜<ArrowRight :size="16" />
              </button></div
          ></template>

          <template v-if="page === 'script' && project"
            ><div class="context-bar">
              <b>已选选题</b
              >{{
                own("story_direction").find((x) => x.data.is_selected)?.name ||
                "请先确认故事方向"
              }}<span class="push-right"
                >{{ activeBrief?.data.duration_min_s }}–{{
                  activeBrief?.data.duration_max_s
                }}
                秒</span
              >
            </div>
            <section class="panel">
              <div class="panel-title">
                <h2>
                  剧情稿
                  <span v-if="currentScript" class="pill"
                    >v{{ currentScript.version }} ·
                    {{ label(currentScript.status) }}</span
                  >
                </h2>
                <button class="text-btn push-right" @click="askAI('script')">
                  <Sparkles :size="16" />AI 生成 / 改写</button
                ><button @click="scriptForm(currentScript)">
                  <NotebookPen :size="16" />{{
                    currentScript ? "编辑剧情" : "手写剧情"
                  }}</button
                ><button
                  v-if="currentScript && currentScript.status !== 'confirmed'"
                  class="primary"
                  @click="confirmScript(currentScript)"
                >
                  <Check :size="16" />确认剧情
                </button>
              </div>
              <p class="script-summary">
                {{
                  currentScript?.data.summary ||
                  "先写出观众能理解的处境、猫咪的行动和情绪落点。"
                }}
              </p>
              <div class="version-links" v-if="own('script').length > 1">
                <details>
                  <summary>历史剧情版本（{{ own("script").length }}）</summary>
                  <article v-for="s in own('script')" :key="s.id">
                    <b>v{{ s.version }} · {{ date(s.created_at) }}</b>
                    <p>{{ s.data.summary }}</p>
                  </article>
                </details>
              </div>
            </section>
            <section class="panel">
              <div class="panel-title">
                <h2>
                  分镜编排
                  <small
                    >{{ shotList.length }} 镜 /
                    {{ shotList.reduce((a, x) => a + x.duration_s, 0) }}
                    秒</small
                  >
                </h2>
                <button
                  class="text-btn push-right"
                  @click="askAI('storyboard')"
                >
                  <Sparkles :size="16" />AI 生成分镜草稿</button
                ><button @click="shotForm()">
                  <Plus :size="16" />添加镜头
                </button>
              </div>
              <div v-if="!shotList.length" class="empty">
                <Clapperboard :size="34" />
                <p>剧情确认后，添加每一镜的动作、时长与声音。</p>
              </div>
              <div class="table-wrap" v-else>
                <table>
                  <thead>
                    <tr>
                      <th>顺序</th>
                      <th>镜头</th>
                      <th>时长与视角</th>
                      <th>动作与结束状态</th>
                      <th>声音 / 台词</th>
                      <th>镜头检查</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(sh, i) in shotList"
                      :key="sh.id"
                      draggable="true"
                      @dragstart="dragId = sh.id"
                      @dragover.prevent
                      @drop.prevent="dropShot(sh)"
                    >
                      <td>
                        <GripVertical :size="15" />{{
                          String(i + 1).padStart(2, "0")
                        }}
                      </td>
                      <td>
                        <b>{{ sh.name }}</b>
                      </td>
                      <td>
                        <b>{{ sh.start }}–{{ sh.end }} 秒</b
                        ><small
                          >{{ sh.duration_s }}s · {{ sh.data.shot_size }} ·
                          {{ sh.data.angle }}</small
                        >
                      </td>
                      <td>
                        {{ sh.data.action
                        }}<small
                          >结束：{{ sh.data.end_state || "待填写" }}</small
                        >
                      </td>
                      <td>
                        {{ sh.data.sound
                        }}<small>{{ sh.data.line_text }}</small>
                      </td>
                      <td>
                        <span
                          class="pill"
                          :class="{
                            amber: !['single', 'anatomy', 'continuity'].every(
                              (k) => sh.data.checks?.[k],
                            ),
                          }"
                          >{{
                            ["single", "anatomy", "continuity"].filter(
                              (k) => sh.data.checks?.[k],
                            ).length
                          }}
                          / 3 通过</span
                        >
                      </td>
                      <td>
                        <div class="row-actions">
                          <button class="text-btn" @click="shotForm(sh)">
                            编辑</button
                          ><button
                            class="icon-btn"
                            @click="moveShot(sh, -1)"
                            aria-label="镜头上移"
                          >
                            ↑</button
                          ><button
                            class="icon-btn"
                            @click="moveShot(sh, 1)"
                            aria-label="镜头下移"
                          >
                            ↓</button
                          ><button
                            class="icon-btn"
                            @click="remove('shot', sh.id)"
                            aria-label="归档镜头"
                          >
                            <Trash2 :size="14" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="hint">
                <Info
                  :size="16"
                />时间区间由镜头顺序和时长自动累加；拖拽行可排序。每镜须完成“单一主动作、猫的身体逻辑、前后衔接”检查。
              </div>
            </section>
            <div class="action-bar">
              <button @click="nav('research')">
                <ArrowLeft :size="16" />素材调研</button
              ><span class="push-right"
                >资产需求会随新增镜头建立，下一步回传与定稿。</span
              ><button class="accent" @click="confirmStage(3)">
                确认分镜，进入数字资产<ArrowRight :size="16" />
              </button></div
          ></template>

          <template v-if="['assets', 'library'].includes(page)"
            ><div class="section-tabs">
              <button
                :class="{ active: !globalAssets }"
                @click="globalAssets = false"
              >
                项目资产</button
              ><button
                :class="{ active: globalAssets }"
                @click="globalAssets = true"
              >
                全局可复用库</button
              ><span class="push-right muted"
                >新版本定稿后，已绑定镜头继续保留旧版本。</span
              >
            </div>
            <div class="asset-layout">
              <section class="panel">
                <div class="chip-row">
                  <button
                    v-for="t in [{ value: 'all', label: '全部' }, ...types]"
                    :key="t.value"
                    :class="{ active: assetType === t.value }"
                    @click="assetType = t.value"
                  >
                    {{ t.label }}
                    <small>{{ t.value === "all" ? assets.length : "" }}</small>
                  </button>
                </div>
                <div class="asset-grid">
                  <article
                    v-for="a in assets"
                    :key="a.id"
                    class="asset-card"
                    :class="{ selected: activeAsset?.id === a.id }"
                    @click="
                      assetId = a.id;
                      avId = '';
                    "
                  >
                    <div class="asset-image">
                      <img
                        v-if="
                          cover(a) &&
                          !['VOICE', 'SFX', 'BGM'].includes(a.data.type)
                        "
                        :src="fileUrl(cover(a))"
                        :alt="a.name"
                      /><Volume2
                        v-else-if="
                          ['VOICE', 'SFX', 'BGM'].includes(a.data.type)
                        "
                        :size="42"
                      /><Images v-else :size="40" /><span class="pill">{{
                        typeLabel(a.data.type)
                      }}</span>
                    </div>
                    <div>
                      <h3>{{ a.name }}</h3>
                      <small
                        >{{ a.data.code }} ·
                        {{ a.project_id ? "项目" : "全局" }}资产</small
                      >
                      <p>
                        <span
                          class="pill"
                          :class="{
                            amber: !list('asset_version').some(
                              (x) =>
                                x.parent_id === a.id && x.status === 'final',
                            ),
                          }"
                          >{{
                            list("asset_version").some(
                              (x) =>
                                x.parent_id === a.id && x.status === "final",
                            )
                              ? "有定稿版本"
                              : "待回传 / 定稿"
                          }}</span
                        >
                      </p>
                    </div>
                  </article>
                </div>
                <div v-if="!assets.length" class="empty large">
                  <Images :size="38" />
                  <h3>从一只稳定的主角开始</h3>
                  <p>创建角色、场景、道具或声音，回传官网素材后定稿。</p>
                  <button class="primary" @click="assetForm">
                    新建数字资产
                  </button>
                </div>
              </section>
              <aside class="panel" v-if="activeAsset">
                <div class="panel-title">
                  <h2>{{ activeAsset.name }}</h2>
                  <span class="pill push-right">{{
                    activeAsset.data.code
                  }}</span>
                </div>
                <p class="note">
                  {{ activeAsset.data.locked_traits || "尚未登记锁定特征" }}
                </p>
                <div class="version-selector">
                  <button
                    v-for="v in versions"
                    :key="v.id"
                    :class="{ active: activeVersion?.id === v.id }"
                    @click="avId = v.id"
                  >
                    v{{ v.version }} · {{ label(v.status) }}</button
                  ><button @click="versionForm">
                    <Plus :size="14" />回传新版本
                  </button>
                </div>
                <template v-if="activeVersion"
                  ><div
                    v-for="f in assetFiles(activeVersion)"
                    :key="f.id"
                    class="asset-detail-image"
                  >
                    <span>{{ f.name }}</span
                    ><audio
                      v-if="f.name === '音频'"
                      controls
                      :src="fileUrl(f.data.file_id)"
                    /><img
                      v-else
                      :src="fileUrl(f.data.file_id)"
                      :alt="activeAsset.name + ' ' + f.name"
                    />
                  </div>
                  <div class="field">
                    <span>对比另一版本</span
                    ><select v-model="assetCompareId">
                      <option value="">关闭版本对比</option>
                      <option
                        v-for="v in versions.filter(
                          (x) => x.id !== activeVersion.id,
                        )"
                        :key="v.id"
                        :value="v.id"
                      >
                        v{{ v.version }} · {{ label(v.status) }}
                      </option>
                    </select>
                  </div>
                  <div v-if="assetCompareId" class="asset-detail-image">
                    <span
                      >对照版本
                      {{ byId("asset_version", assetCompareId)?.version }}</span
                    ><template
                      v-for="f in assetFiles(
                        byId('asset_version', assetCompareId),
                      )"
                      :key="f.id"
                      ><audio
                        v-if="f.name === '音频'"
                        controls
                        :src="fileUrl(f.data.file_id)" /><img
                        v-else
                        :src="fileUrl(f.data.file_id)"
                        alt="对照版本素材"
                    /></template>
                  </div>
                  <button
                    v-if="activeVersion.status !== 'final'"
                    class="text-btn"
                    @click="addAssetFile"
                  >
                    <Plus :size="14" />补充表情 / 细节图位
                  </button>
                  <dl class="definition">
                    <dt>来源</dt>
                    <dd>{{ activeVersion.data.source }}</dd>
                    <dt>授权</dt>
                    <dd>{{ activeVersion.data.license_note || "未填写" }}</dd>
                    <dt>官网主体</dt>
                    <dd>
                      <p
                        v-for="p in list('platform_subject').filter(
                          (x) => x.parent_id === activeVersion.id,
                        )"
                        :key="p.id"
                      >
                        {{
                          byId("model_profile", p.data.model_profile_id)?.name
                        }}：@{{ p.name }}
                      </p>
                      <button class="text-btn" @click="subjectForm">
                        登记主体名
                      </button>
                    </dd>
                  </dl>
                  <button
                    v-if="activeVersion.status !== 'final'"
                    class="primary full-width"
                    @click="finalizeAsset"
                  >
                    <Check :size="16" />设为定稿
                  </button>
                  <div v-else class="hint success">
                    <ShieldCheck :size="16" />定稿文件已锁定，修改请回传新版本。
                  </div></template
                >
                <div class="panel-title inner">
                  <h2>生图提示词</h2>
                  <button
                    class="text-btn push-right"
                    @click="
                      askAI(
                        activeAsset.data.type === 'CHAR'
                          ? 'portrait'
                          : activeAsset.data.type === 'SCN'
                            ? 'scene'
                            : 'prop',
                        { asset: activeAsset },
                      )
                    "
                  >
                    <Sparkles :size="14" />AI 草稿
                  </button>
                </div>
                <textarea
                  :value="
                    activeAsset.data.prompt || activeVersion?.data.prompt || ''
                  "
                  rows="5"
                  readonly
                  placeholder="可用 AI 草拟，或回传时记录官网使用的提示词。"
                /><button
                  class="full-width"
                  @click="
                    copy(
                      activeAsset.data.prompt ||
                        activeVersion?.data.prompt ||
                        '',
                    )
                  "
                >
                  <Copy :size="14" />复制生图提示词
                </button>
              </aside>
            </div>
            <section v-if="project && page === 'assets'" class="panel">
              <div class="panel-title">
                <h2>本片必需资产清单</h2>
                <span class="muted"
                  >按每镜的主体、场景、道具需求关联定稿版本</span
                >
              </div>
              <div class="requirements-grid">
                <div v-for="bind in own('shot_binding')" :key="bind.id">
                  <span
                    ><b>{{ byId("shot", bind.shot_id)?.name }}</b> /
                    {{ bind.data.slot }}</span
                  ><select
                    :value="bind.data.asset_version_id || ''"
                    @change="assignRequirement(bind, $event.target.value)"
                  >
                    <option value="">请选择已定稿资产版本</option>
                    <option
                      v-for="v in optionsForSlot(bind.data.slot)"
                      :key="v.id"
                      :value="v.id"
                    >
                      {{ versionLabel(v) }}
                    </option>
                  </select>
                </div>
              </div>
              <p v-if="!own('shot_binding').length" class="note">
                请先在分镜页添加镜头，系统会建立对应需求。
              </p>
            </section>
            <div v-if="project && page === 'assets'" class="action-bar">
              <button @click="nav('script')">
                <ArrowLeft :size="16" />剧本分镜</button
              ><span class="push-right"
                >未定稿的必需资产会阻止进入视频生成。</span
              ><button class="accent" @click="confirmStage(4)">
                确认资产，进入模型设置<ArrowRight :size="16" />
              </button></div
          ></template>

          <template v-if="page === 'models' && project"
            ><div class="two-col">
              <section class="panel">
                <div class="panel-title">
                  <h2>项目默认模型</h2>
                  <button class="text-btn push-right" @click="nav('settings')">
                    管理档案<ExternalLink :size="13" />
                  </button>
                </div>
                <div class="model-card-grid">
                  <button
                    v-for="m in activeModels"
                    :key="m.id"
                    class="model-card"
                    :class="{ selected: generation.default_model_id === m.id }"
                    @click="generation.default_model_id = m.id"
                  >
                    <Layers :size="28" />
                    <h3>{{ m.name }}</h3>
                    <span
                      class="pill"
                      :class="{ amber: !m.data.verified_at }"
                      >{{
                        m.data.verified_at
                          ? "已核对 " + m.data.verified_at
                          : "未核对档案"
                      }}</span
                    ><small>版本：{{ m.data.version || "待填写" }}</small
                    ><a
                      :href="m.data.site_url"
                      target="_blank"
                      rel="noopener noreferrer"
                      @click.stop
                      >打开官网<ExternalLink :size="12"
                    /></a>
                  </button>
                </div>
                <div class="panel-title inner"><h2>通用生成偏好</h2></div>
                <div class="form-grid">
                  <label class="field"
                    ><span>生成方式</span
                    ><select v-model="generation.mode">
                      <option>参考生视频</option>
                      <option>图生视频</option>
                      <option>文生视频</option>
                    </select></label
                  ><label class="field"
                    ><span>试做分辨率</span
                    ><input
                      v-model="generation.resolution"
                      placeholder="例如 720p，须与档案一致" /></label
                  ><label class="field"
                    ><span>每镜候选数</span
                    ><input
                      type="number"
                      v-model.number="generation.candidates"
                      min="1"
                      max="10" /></label
                  ><label class="field"
                    ><span>音频策略</span
                    ><select v-model="generation.audio_strategy">
                      <option>后期补充</option>
                      <option>保留原生声音，台词后配</option>
                      <option>原生音频</option>
                    </select></label
                  >
                </div>
                <button class="primary" @click="saveGeneration">
                  保存生成偏好
                </button>
                <div class="panel-title inner"><h2>逐镜模型安排</h2></div>
                <div class="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>镜头</th>
                        <th>目标时长</th>
                        <th>覆盖模型</th>
                        <th>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="sh in shotList" :key="sh.id">
                        <td>{{ sh.seq + 1 }} · {{ sh.name }}</td>
                        <td>{{ sh.duration_s }}s</td>
                        <td>
                          <select
                            :value="sh.data.model_profile_id || ''"
                            @change="shotModel(sh, $event.target.value)"
                          >
                            <option value="">跟随项目默认</option>
                            <option
                              v-for="m in activeModels"
                              :key="m.id"
                              :value="m.id"
                            >
                              {{ m.name }}
                            </option>
                          </select>
                        </td>
                        <td>
                          <span class="status" :class="sh.status">{{
                            label(sh.status)
                          }}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p class="note">
                  修改默认模型不会覆盖单镜设置。所有能力在导出时再次按档案校验。
                </p>
              </section>
              <aside class="panel">
                <h2>本片生成计划</h2>
                <dl class="definition">
                  <dt>目标成片</dt>
                  <dd>
                    {{ shotList.reduce((a, x) => a + x.duration_s, 0) }} 秒 /
                    {{ activeBrief?.data.aspect_ratio }}
                  </dd>
                  <dt>镜头数量</dt>
                  <dd>{{ shotList.length }} 镜</dd>
                  <dt>项目预算</dt>
                  <dd>{{ yuan(activeBrief?.data.budget_cap) }}</dd>
                  <dt>已记花费</dt>
                  <dd>{{ yuan(spent(projectId)) }}</dd>
                </dl>
                <div class="next-note">
                  <ShieldCheck :size="22" />
                  <div>
                    <b>导出前需完成</b>
                    <p>
                      核对模型档案、绑定定稿素材、确认预计费用。平台不调用图片或视频生成接口。
                    </p>
                  </div>
                </div>
                <button class="full-width" @click="nav('bindings')">
                  去绑定单镜素材<ArrowRight :size="16" />
                </button>
              </aside>
            </div>
            <div class="action-bar">
              <button @click="nav('assets')">
                <ArrowLeft :size="16" />数字资产</button
              ><span class="push-right">计划先保存，导出前核对能力与费用。</span
              ><button
                class="accent"
                @click="saveGeneration().then(() => nav('bindings'))"
              >
                保存并进入素材绑定<ArrowRight :size="16" />
              </button></div
          ></template>

          <template v-if="['bindings', 'review'].includes(page) && project"
            ><div v-if="!shotList.length" class="empty large">
              <Clapperboard :size="40" />
              <h3>请先添加分镜</h3>
              <button @click="nav('script')">进入剧本分镜</button>
            </div>
            <div class="shot-workspace" v-else>
              <aside class="panel shot-sidebar">
                <h2>本项目镜头</h2>
                <button
                  v-for="sh in shotList"
                  :key="sh.id"
                  class="shot-nav"
                  :class="{ active: activeShot?.id === sh.id }"
                  @click="shotId = sh.id"
                >
                  <span class="shot-number">{{
                    String(sh.seq + 1).padStart(2, "0")
                  }}</span>
                  <div>
                    <b>{{ sh.name }}</b
                    ><small>{{ sh.start }}–{{ sh.end }} 秒</small
                    ><span class="status" :class="sh.status">{{
                      label(sh.status)
                    }}</span>
                  </div>
                </button>
                <div class="note">
                  {{ selectedCount }} / {{ shotList.length }} 镜已选用
                </div>
              </aside>
              <template v-if="page === 'bindings'"
                ><section class="panel">
                  <div class="panel-title">
                    <h2>{{ activeShot?.name }}</h2>
                    <span class="pill push-right"
                      >目标 {{ activeShot?.duration_s }} 秒</span
                    >
                  </div>
                  <div class="shot-description">
                    <b>动作：</b>{{ activeShot?.data.action }}<br /><b>结束：</b
                    >{{ activeShot?.data.end_state }}
                  </div>
                  <div class="panel-title">
                    <h3>本镜素材</h3>
                    <button
                      class="text-btn push-right"
                      v-if="!binds.some((x) => x.data.slot === '声音')"
                      @click="addAudioBinding"
                    >
                      添加可选声音参考
                    </button>
                  </div>
                  <div v-for="b in binds" :key="b.id" class="binding-card">
                    <div class="binding-label">
                      <b>{{ b.data.slot }}</b
                      ><em>{{ b.data.required ? "必选" : "可选" }}</em>
                    </div>
                    <div class="flex-grow">
                      <select
                        :value="b.data.asset_version_id || ''"
                        @change="assignRequirement(b, $event.target.value)"
                      >
                        <option value="">选择定稿版本</option>
                        <option
                          v-for="v in optionsForSlot(b.data.slot)"
                          :value="v.id"
                          :key="v.id"
                        >
                          {{ versionLabel(v) }}
                        </option></select
                      ><label v-if="b.data.slot === '主体'" class="check-field"
                        ><input
                          type="checkbox"
                          :checked="b.data.with_accessories"
                          @change="
                            act(() =>
                              save(
                                'shot_binding',
                                {
                                  data: {
                                    ...b.data,
                                    with_accessories: $event.target.checked,
                                  },
                                },
                                b.id,
                              ),
                            )
                          "
                        />固定配饰随角色引用</label
                      >
                    </div>
                    <Check
                      v-if="b.data.asset_version_id"
                      :size="18"
                      class="green"
                    />
                  </div>
                  <div class="panel-title inner">
                    <h2>视频提示词</h2>
                    <button
                      class="text-btn push-right"
                      @click="askAI('video_prompt', { shot: activeShot })"
                    >
                      <Sparkles :size="14" />AI 草稿</button
                    ><button @click="shotForm(activeShot)">编辑</button>
                  </div>
                  <pre class="prompt-text">{{
                    activeShot?.data.prompt ||
                    "请填写包含主体、场景、道具占位符的视频提示词。"
                  }}</pre>
                  <p class="note">
                    音频参考可在声音资产中管理；后期配音不作为本镜强制项。
                  </p>
                </section>
                <aside class="panel">
                  <div class="panel-title">
                    <h2>提交包预览</h2>
                    <button class="text-btn push-right" @click="loadPreview">
                      <RefreshCw :size="15" />校验
                    </button>
                  </div>
                  <template v-if="preview"
                    ><h3>替换后的提示词</h3>
                    <pre class="prompt-text">{{ preview.prompt }}</pre>
                    <button class="full-width" @click="copy(preview.prompt)">
                      <Copy :size="14" />复制最终提示词
                    </button>
                    <h3 class="mt">上传顺序与 @ 对照</h3>
                    <div
                      v-for="u in preview.upload_order"
                      :key="u.order"
                      class="upload-order"
                    >
                      <span class="num">{{ u.order }}</span>
                      <div>
                        <b>{{ u.filename }}</b
                        ><small>{{
                          u.subject
                            ? "手动点选 @" + u.subject
                            : "引用图" + u.order
                        }}</small>
                      </div>
                    </div>
                    <dl class="definition">
                      <dt>模型版本</dt>
                      <dd>
                        {{ preview.params.model }}
                        {{ preview.params.model_version }}
                      </dd>
                      <dt>生成参数</dt>
                      <dd>
                        {{ preview.params.ratio }} /
                        {{ preview.params.duration_s }}s /
                        {{ preview.params.resolution }}
                      </dd>
                      <dt>候选与估算</dt>
                      <dd>
                        {{ preview.params.candidates }} 个 /
                        {{
                          preview.estimate_cny === null
                            ? "未定价"
                            : yuan(preview.estimate_cny)
                        }}
                      </dd>
                    </dl>
                    <div
                      v-for="e in preview.errors"
                      :key="e"
                      class="error-text"
                    >
                      {{ e }}
                    </div>
                    <div v-if="!preview.errors.length" class="hint success">
                      <Check :size="17" />引用与档案能力校验通过
                    </div></template
                  >
                  <div v-else class="empty">
                    <ShieldCheck :size="35" />
                    <p>
                      点击校验，检查素材引用、官网主体、上传顺序和模型能力。
                    </p>
                  </div>
                  <button class="accent full-width" @click="exportShot">
                    <Download :size="16" />导出本镜提交包
                  </button>
                  <p class="note">
                    导出即冻结提示词、素材版本与参数，不会在官网自动提交。
                  </p>
                </aside></template
              >
              <template v-else
                ><section class="panel review-main">
                  <div class="panel-title">
                    <h2>
                      {{ activeShot?.name }}
                      <span v-if="candidate" class="pill"
                        >候选 {{ candidate.name }}</span
                      >
                    </h2>
                    <button class="text-btn push-right" @click="exportShot">
                      <Download :size="15" />再导出一次</button
                    ><button class="primary" @click="ingestCandidate()">
                      <Upload :size="16" />回传候选
                    </button>
                  </div>
                  <div v-if="!candidate" class="empty large">
                    <Upload :size="40" />
                    <h3>把官网生成的候选带回来</h3>
                    <p>
                      先导出提交包，在官网粘贴提示词、上传对应素材，再回传视频。
                    </p>
                    <button @click="nav('bindings')">检查绑定与导出</button>
                  </div>
                  <template v-else
                    ><div class="video-comparison">
                      <video
                        ref="videoPlayer"
                        :src="fileUrl(candidate.data.file_id)"
                        controls
                        preload="metadata"
                      /><video
                        v-if="compareCandidate"
                        ref="comparePlayer"
                        :src="fileUrl(compareCandidate.data.file_id)"
                        controls
                        preload="metadata"
                      />
                    </div>
                    <div class="player-tools">
                      <button @click="frameStep(-1)">上一帧</button
                      ><button @click="frameStep(1)">下一帧</button
                      ><button @click="download(candidate.data.file_id)">
                        <Download :size="14" />下载原视频</button
                      ><select v-model="compareId" aria-label="对比候选">
                        <option value="">选择另一候选并排对比</option>
                        <option
                          v-for="c in candidates.filter(
                            (x) => x.id !== candidate.id,
                          )"
                          :key="c.id"
                          :value="c.id"
                        >
                          {{ c.name }}
                        </option>
                      </select>
                    </div>
                    <div class="media-meta">
                      <span
                        >{{ candidate.data.media_meta?.width || "—" }} ×
                        {{ candidate.data.media_meta?.height || "—" }}</span
                      ><span
                        >{{
                          candidate.data.media_meta?.duration?.toFixed(2) ||
                          "—"
                        }}s</span
                      ><span
                        >{{
                          candidate.data.media_meta?.fps?.toFixed(2) || "—"
                        }}fps</span
                      ><span>{{
                        candidate.data.media_meta?.has_audio
                          ? "含音轨"
                          : "无音轨 / 后期补充"
                      }}</span
                      ><span>{{
                        candidate.data.analysis_status === "ready"
                          ? "检测完成"
                          : candidate.data.analysis_status === "failed"
                            ? "检测失败"
                            : "后台检测中"
                      }}</span>
                    </div>
                    <div
                      v-if="candidate.data.analysis_error"
                      class="error-text"
                    >
                      {{ candidate.data.analysis_error }}
                      <button
                        @click="
                          act(() =>
                            api(
                              '/candidates/' + candidate.id + '/reanalyze',
                              'POST',
                            ),
                          )
                        "
                      >
                        重新检测
                      </button>
                    </div>
                    <div
                      v-for="e in candidate.data.mismatch"
                      :key="e"
                      class="hint warning"
                    >
                      {{ e }}
                    </div>
                    <details
                      v-if="candidate.data.frame_ids?.length"
                      class="frame-browser"
                    >
                      <summary>
                        每 0.5 秒抽帧查看（{{ candidate.data.frame_ids.length }}
                        张）
                      </summary>
                      <input
                        type="range"
                        min="0"
                        :max="candidate.data.frame_ids.length - 1"
                        v-model.number="frame"
                      /><img
                        :src="fileUrl(candidate.data.frame_ids[frame])"
                        :alt="'第' + (frame + 1) + '张抽帧'"
                      /><small>{{ (frame * 0.5).toFixed(1) }} 秒</small>
                    </details>
                    <div class="candidate-strip">
                      <button
                        v-for="c in candidates"
                        :key="c.id"
                        :class="{ active: candidate.id === c.id }"
                        @click="candidateId = c.id"
                      >
                        <img
                          v-if="c.data.frame_ids?.length"
                          :src="fileUrl(c.data.frame_ids[0])"
                          :alt="c.name"
                        /><span
                          >{{ c.name
                          }}<small>{{ label(c.status) }}</small></span
                        >
                      </button>
                    </div></template
                  >
                  <details class="generation-history">
                    <summary>冻结提交记录（{{ gens.length }}）</summary>
                    <div v-for="g in gens" :key="g.id" class="record-row">
                      <span
                        >{{ date(g.created_at) }} · {{ g.data.params.model }} ·
                        {{ label(g.status) }}</span
                      ><button @click="download(g.data.package_file_id)">
                        下载原提交包
                      </button>
                      <details>
                        <summary>提示词与参数快照</summary>
                        <pre>{{ JSON.stringify(g.data, null, 2) }}</pre>
                      </details>
                    </div>
                  </details>
                </section>
                <aside class="panel" v-if="candidate">
                  <h2>人工审片</h2>
                  <p class="muted">审核对象：候选 {{ candidate.name }}</p>
                  <label
                    v-for="c in reviewChecklist"
                    :key="c.value"
                    class="check-field review-check"
                    ><input type="checkbox" v-model="reviewChecks[c.value]" />{{
                      c.label
                    }}</label
                  >
                  <h3 class="mt">问题与修改意见</h3>
                  <label class="field"
                    ><span>问题时间点（秒）</span
                    ><input
                      type="number"
                      min="0"
                      v-model.number="issueTime" /></label
                  ><textarea
                    v-model="issue"
                    rows="4"
                    placeholder="例如：第 2 秒前爪穿过道具，需重写提示词。"
                  />
                  <div class="review-actions">
                    <button class="primary" @click="review('selected')">
                      <Check :size="16" />通过并选用</button
                    ><button @click="review('rejected')">淘汰</button
                    ><button @click="review('rewrite')">重写提示词</button>
                  </div>
                  <div class="panel-title inner"><h2>画质增强登记</h2></div>
                  <p class="note">
                    选用后可导出增强参数，在外部增强工具处理，再回传子版本。原版保留，费用单独记录。
                  </p>
                  <button
                    class="full-width"
                    :disabled="candidate.status !== 'selected'"
                    @click="enhancementExport"
                  >
                    导出增强参数</button
                  ><button
                    class="full-width"
                    :disabled="candidate.status !== 'selected'"
                    @click="ingestCandidate(true)"
                  >
                    <Upload :size="15" />回传增强版
                  </button>
                  <div class="hint">
                    <Info
                      :size="16"
                    />检测与分辨率不能替代动作、角色一致性和实际试听。
                  </div>
                </aside></template
              >
            </div>
            <div class="action-bar">
              <button @click="nav('models')">
                <ArrowLeft :size="16" />模型设置</button
              ><span class="push-right"
                >本片 {{ selectedCount }} / {{ shotList.length }} 镜已选用</span
              ><button class="accent" @click="confirmStage(5)">
                全部镜头选用，进入剪辑准备<ArrowRight :size="16" />
              </button></div
          ></template>

          <template v-if="page === 'progress' && project"
            ><div class="stats-row">
              <div
                class="stat"
                v-for="(v, i) in [
                  selectedCount,
                  own('generation_record').filter(
                    (x) => x.status === 'awaiting',
                  ).length,
                  own('candidate').filter((x) => x.status === 'pending').length,
                  spent(projectId),
                ]"
                :key="i"
              >
                <span class="stat-icon"
                  ><component
                    :is="[CheckCheck, Clock, Clapperboard, Wallet][i]"
                    :size="23"
                /></span>
                <div>
                  <p>
                    {{
                      [
                        "已选用镜头",
                        "待回传提交包",
                        "待审片候选",
                        "本片已记花费",
                      ][i]
                    }}
                  </p>
                  <strong>{{ i === 3 ? yuan(v) : v }}</strong>
                </div>
              </div>
            </div>
            <div class="two-col">
              <section class="panel">
                <div class="panel-title">
                  <h2>本项目镜头</h2>
                  <select v-model="filter" class="push-right">
                    <option value="all">全部状态</option>
                    <option
                      v-for="s in [
                        'draft',
                        'binding',
                        'ready',
                        'awaiting',
                        'review',
                        'selected',
                      ]"
                      :value="s"
                      :key="s"
                    >
                      {{ label(s) }}
                    </option></select
                  ><a
                    class="button"
                    :href="'/api/projects/' + projectId + '/todo'"
                    ><Download :size="15" />导出待办清单</a
                  >
                </div>
                <div class="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>镜头</th>
                        <th>模型安排</th>
                        <th>状态</th>
                        <th>候选</th>
                        <th>已花费</th>
                        <th>下一步</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="sh in shotList.filter(
                          (x) => filter === 'all' || x.status === filter,
                        )"
                        :key="sh.id"
                      >
                        <td>
                          <b>{{ sh.seq + 1 }} {{ sh.name }}</b
                          ><small>{{ sh.start }}–{{ sh.end }} 秒</small>
                        </td>
                        <td>
                          {{
                            byId(
                              "model_profile",
                              sh.data.model_profile_id ||
                                project.data.default_model_id,
                            )?.name || "待选择"
                          }}
                        </td>
                        <td>
                          <span class="status" :class="sh.status">{{
                            label(sh.status)
                          }}</span>
                        </td>
                        <td>
                          {{
                            own("candidate").filter((x) => x.shot_id === sh.id)
                              .length
                          }}
                        </td>
                        <td>
                          {{
                            yuan(
                              own("cost_entry")
                                .filter((c) =>
                                  own("candidate").some(
                                    (x) =>
                                      x.shot_id === sh.id &&
                                      x.id === c.parent_id,
                                  ),
                                )
                                .reduce((a, x) => a + x.amount_fen / 100, 0),
                            )
                          }}
                        </td>
                        <td>
                          <button
                            @click="
                              nav(
                                ['review', 'awaiting', 'selected'].includes(
                                  sh.status,
                                )
                                  ? 'review'
                                  : 'bindings',
                              );
                              shotId = sh.id;
                            "
                          >
                            {{
                              ["review", "awaiting", "selected"].includes(
                                sh.status,
                              )
                                ? "回传 / 审片"
                                : "绑定 / 导出"
                            }}
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-if="!shotList.length" class="empty">
                  <p>先去剧本页添加分镜。</p>
                  <button @click="nav('script')">添加分镜</button>
                </div>
              </section>
              <aside class="panel">
                <h2>本片花费汇总</h2>
                <dl class="definition">
                  <template v-for="m in list('model_profile')" :key="m.id"
                    ><dt>{{ m.name }}</dt>
                    <dd>
                      {{
                        yuan(
                          own("cost_entry")
                            .filter((x) => x.data.model_profile_id === m.id)
                            .reduce((a, x) => a + x.amount_fen / 100, 0),
                        )
                      }}
                    </dd></template
                  >
                  <dt>全部记账</dt>
                  <dd>
                    <b>{{ yuan(spent(projectId)) }}</b>
                  </dd>
                  <dt>项目预算</dt>
                  <dd>{{ yuan(activeBrief?.data.budget_cap) }}</dd>
                </dl>
                <button class="full-width" @click="nav('costs')">
                  查看费用流水<ArrowRight :size="15" />
                </button>
                <p class="note">
                  没有自动生成队列，待办清单供你在官网逐镜手动操作。
                </p>
              </aside>
            </div>
            <div class="action-bar">
              <span class="push-right">全部镜头选用后，可打包交给剪映。</span
              ><button class="accent" @click="confirmStage(5)">
                确认镜头，进入剪辑准备<ArrowRight :size="16" />
              </button></div
          ></template>

          <template v-if="page === 'placement' && project"
            ><section class="panel">
              <div class="panel-title">
                <h2>商品作为剧情道具</h2>
                <span class="pill amber">可选支线</span
                ><button class="accent push-right" @click="placementForm">
                  <Plus :size="16" />创建植入方案</button
                ><button @click="nav('review')">跳过植入，继续制作</button>
              </div>
              <p class="muted">
                先在数字资产中创建并定稿商品，核对包装特征，再替换指定镜头的道具版本。原候选保留为历史，其他镜头继续使用原绑定。
              </p>
              <div v-if="!own('placement').length" class="empty large">
                <Layers :size="40" />
                <h3>让商品自然进入动作</h3>
                <p>只改一镜道具与提示词引用，替换后重新导出并审片。</p>
              </div>
              <div v-for="p in own('placement')" :key="p.id" class="record-row">
                <b>{{ byId("shot", p.shot_id)?.name }}</b>
                <p>{{ p.data.exposure }} · {{ p.data.keep_features }}</p>
                <span class="pill">已替换，待重新生成</span>
              </div>
            </section></template
          >

          <template v-if="page === 'edit' && project"
            ><div class="edit-layout">
              <section class="panel">
                <h2>选用镜头</h2>
                <button
                  class="shot-nav"
                  v-for="(sh, i) in shotList"
                  :key="sh.id"
                  :class="{ active: playlistIndex === i }"
                  @click="playlistIndex = i"
                >
                  <span class="shot-number">{{ i + 1 }}</span
                  ><span
                    ><b>{{ sh.name }}</b
                    ><small
                      >{{ sh.duration_s }}s ·
                      {{ selected(sh.id) ? "已选用" : "未选用" }}</small
                    ></span
                  >
                </button>
                <div class="hint">
                  <Info :size="16" />增强版通过审片后，素材包会优先选取增强版。
                </div>
              </section>
              <section class="panel">
                <div class="panel-title">
                  <h2>顺序连播检查</h2>
                  <span class="pill push-right">只读预览</span>
                </div>
                <video
                  v-if="playlist[playlistIndex]"
                  class="edit-video"
                  :src="fileUrl(playlist[playlistIndex].data.file_id)"
                  controls
                  @ended="playlistIndex = (playlistIndex + 1) % playlist.length"
                />
                <div v-else class="empty large">
                  <Video :size="36" />
                  <p>请先为本片镜头选用候选。</p>
                </div>
                <div class="panel-title inner">
                  <h2>镜头 / 声音 / 字幕对照</h2>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>镜头</th>
                      <th>声音要求</th>
                      <th>台词 / 心声</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="sh in shotList" :key="sh.id">
                      <td>{{ sh.start }}–{{ sh.end }}s</td>
                      <td>{{ sh.name }}</td>
                      <td>{{ sh.data.sound }}</td>
                      <td>{{ sh.data.line_text || "—" }}</td>
                    </tr>
                  </tbody>
                </table>
              </section>
              <aside class="panel">
                <div class="panel-title">
                  <h2>字幕初稿 SRT</h2>
                  <button class="text-btn push-right" @click="regenerateSrt">
                    按分镜重建
                  </button>
                </div>
                <p class="note">
                  由镜头时间与台词生成，需在剪映内按实际配音校对。
                </p>
                <textarea class="code-text" v-model="srt" rows="12" />
                <h3 class="mt">剪辑说明与声音要求</h3>
                <textarea
                  v-model="editNotes"
                  rows="5"
                  placeholder="例如：对白时压低 BGM，保留爪子触碰道具的音效。"
                /><button class="full-width" @click="saveEdit">
                  保存字幕与说明
                </button>
                <h3 class="mt">声音授权清单</h3>
                <p
                  v-for="a in list('asset').filter(
                    (x) =>
                      [null, projectId].includes(x.project_id) &&
                      ['VOICE', 'SFX', 'BGM'].includes(x.data.type),
                  )"
                  :key="a.id"
                  class="note"
                >
                  {{ a.name }} ·
                  {{
                    list("asset_version")
                      .filter(
                        (v) => v.parent_id === a.id && v.status === "final",
                      )
                      .at(-1)?.data.license_note || "未定稿 / 缺少授权"
                  }}
                </p>
                <p class="note">
                  素材包包含选用视频、声音文件、SRT
                  与剪辑说明。剪映草稿工程兼容性未验证，本版提供通用素材包。
                </p>
              </aside>
            </div>
            <div class="action-bar">
              <button @click="nav('review')">
                <ArrowLeft :size="16" />镜头审片</button
              ><span class="push-right"
                >在剪映内完成剪辑、配音、字幕与编码导出。</span
              ><button class="primary" @click="exportEdit">
                <Download :size="16" />导出剪映素材包</button
              ><button class="accent" @click="nav('delivery')">
                去回传成片<ArrowRight :size="16" />
              </button></div
          ></template>

          <template v-if="page === 'delivery' && project"
            ><div class="delivery-layout">
              <section class="panel">
                <div class="panel-title">
                  <h2>成片预览</h2>
                  <button class="primary push-right" @click="ingestFinal">
                    <Upload :size="16" />上传剪映成片
                  </button>
                </div>
                <video
                  v-if="activeFinal"
                  class="final-video"
                  :src="fileUrl(activeFinal.data.file_id)"
                  controls
                />
                <div v-else class="empty large">
                  <Video :size="40" />
                  <h3>把剪映完成的作品带回来</h3>
                  <p>上传后自动检测，再由你完整观看、试听、核字幕。</p>
                </div>
                <select
                  v-if="finals.length"
                  v-model="finalId"
                  class="full-width"
                  aria-label="预览成片版本"
                >
                  <option value="">最新成片</option>
                  <option v-for="f in finals" :key="f.id" :value="f.id">
                    {{ f.data.edit_version }} · {{ f.name }} ·
                    {{ label(f.status) }}
                  </option>
                </select>
              </section>
              <section class="panel">
                <h2>成片检查</h2>
                <template v-if="activeFinal"
                  ><div class="panel-title inner">
                    <h3>自动检测</h3>
                    <span class="pill push-right">{{
                      activeFinal.data.analysis_status === "ready"
                        ? "已检测"
                        : activeFinal.data.analysis_status === "failed"
                          ? "检测失败"
                          : "后台检测中"
                    }}</span>
                  </div>
                  <div
                    v-for="(v, k) in activeFinal.data.auto_checks?.checks"
                    :key="k"
                    class="check-result"
                  >
                    <Check v-if="v" :size="16" class="green" /><Info
                      v-else
                      :size="16"
                      class="orange"
                    /><span>{{
                      {
                        ratio: "画幅一致",
                        resolution: "分辨率达到简报要求",
                        duration: "时长在目标范围",
                        audio: "音轨存在",
                        black: "未检出黑帧",
                        silence: "未检出静音段",
                        srt: "SRT 可读",
                      }[k]
                    }}</span
                    ><b>{{ v ? "通过" : "需检查" }}</b>
                  </div>
                  <p class="error-text" v-if="activeFinal.data.analysis_error">
                    {{ activeFinal.data.analysis_error }}
                  </p>
                  <p
                    class="warning-text"
                    v-for="b in activeFinal.data.auto_checks?.black_segments"
                    :key="b.start"
                  >
                    黑帧 {{ b.start }}–{{ b.end }} 秒
                  </p>
                  <p
                    class="warning-text"
                    v-for="t in activeFinal.data.auto_checks?.silence_starts"
                    :key="t"
                  >
                    静音段起点 {{ t }} 秒
                  </p>
                  <button
                    class="text-btn"
                    @click="
                      act(() =>
                        api('/finals/' + activeFinal.id + '/reanalyze', 'POST'),
                      )
                    "
                  >
                    <RefreshCw :size="14" />重新检测
                  </button>
                  <div class="panel-title inner">
                    <h3>人工确认</h3>
                    <span class="pill amber push-right">需实际看片与试听</span>
                  </div>
                  <label class="check-field review-check"
                    ><input
                      type="checkbox"
                      v-model="finalChecks.motion"
                    />完整观看，动作与角色自然</label
                  ><label class="check-field review-check"
                    ><input
                      type="checkbox"
                      v-model="finalChecks.audio"
                    />实际试听，台词清晰、音乐不盖声</label
                  ><label class="check-field review-check"
                    ><input
                      type="checkbox"
                      v-model="finalChecks.subtitle"
                    />字幕文字正确，与配音同步</label
                  ><button class="accent full-width" @click="confirmFinal">
                    <ShieldCheck :size="16" />确认检查，标记可发布
                  </button></template
                >
                <p v-else class="note">自动检查结果会在成片回传后显示。</p>
              </section>
              <aside class="panel">
                <h2>交付版本与记录</h2>
                <div
                  v-for="f in finals"
                  :key="f.id"
                  class="final-record"
                  :class="{ selected: activeFinal?.id === f.id }"
                  @click="finalId = f.id"
                >
                  <Video :size="20" />
                  <div>
                    <b>{{ f.data.edit_version }} · {{ f.name }}</b
                    ><small
                      >{{ label(f.status) }} · {{ date(f.created_at) }}</small
                    ><small
                      >素材包：v{{
                        byId("edit_package", f.parent_id)?.version
                      }}
                      · {{ f.parent_id.slice(0, 8) }}</small
                    >
                  </div>
                  <button
                    class="icon-btn"
                    @click.stop="download(f.data.file_id)"
                    aria-label="下载成片"
                  >
                    <Download :size="16" />
                  </button>
                </div>
                <h3 class="mt">工程与记录</h3>
                <div
                  v-for="ep in own('edit_package')"
                  :key="ep.id"
                  class="record-row"
                >
                  <span>剪映素材包 v{{ ep.version }}</span
                  ><button class="text-btn" @click="download(ep.data.file_id)">
                    下载
                  </button>
                </div>
                <button
                  :disabled="activeFinal?.status !== 'publishable'"
                  class="primary full-width"
                  @click="archiveFinal"
                >
                  <Download :size="16" />打包交付归档
                </button>
                <p class="note">
                  归档包含成片、资产与授权清单、冻结提示词、模型参数与质检记录，不含
                  API 密钥。
                </p>
                <button class="full-width" @click="releaseForm">
                  <Link :size="16" />登记手动发布链接
                </button>
              </aside>
            </div>
            <div class="action-bar">
              <button @click="nav('edit')">
                <ArrowLeft :size="16" />返回剪辑准备</button
              ><span class="push-right"
                >技术检测通过仍需实际试听与完整观看。</span
              ><button class="accent" @click="confirmStage(6)">
                确认交付，进入数据复盘<ArrowRight :size="16" />
              </button></div
          ></template>

          <template v-if="page === 'retro' && project"
            ><div class="context-bar">
              <b>发布记录</b
              ><select
                :value="activeRelease?.id || ''"
                @change="releaseId = $event.target.value"
              >
                <option value="">请选择发布版本</option>
                <option v-for="r in own('release')" :key="r.id" :value="r.id">
                  {{ r.name }} · {{ date(r.data.published_at) }}
                </option></select
              ><a
                v-if="activeRelease"
                :href="activeRelease.data.url"
                target="_blank"
                rel="noopener noreferrer"
                >查看发布链接<ExternalLink :size="12" /></a
              ><select v-model="metricSnapshotId" aria-label="统计窗口快照">
                <option value="">最新统计窗口</option>
                <option
                  v-for="m in own('metric_snapshot').filter(
                    (x) => x.parent_id === activeRelease?.id,
                  )"
                  :key="m.id"
                  :value="m.id"
                >
                  {{ m.data.period }} · {{ date(m.created_at) }}
                </option></select
              ><button @click="nav('compare')">跨视频对比</button
              ><button class="push-right" @click="releaseForm">
                <Plus :size="15" />登记发布</button
              ><button class="primary" @click="csvForm">
                <Upload :size="15" />导入指标 CSV
              </button>
            </div>
            <section v-if="csvData" class="panel">
              <div class="panel-title">
                <h2>CSV 预览与字段映射</h2>
                <span class="pill">{{ csvData.total }} 行</span
                ><button class="text-btn push-right" @click="csvData = null">
                  关闭
                </button>
              </div>
              <div class="form-grid">
                <label class="field"
                  ><span>发布版本</span
                  ><select v-model="csvRelease">
                    <option
                      v-for="r in own('release')"
                      :key="r.id"
                      :value="r.id"
                    >
                      {{ r.name }} · {{ date(r.data.published_at) }}
                    </option>
                  </select></label
                ><label class="field"
                  ><span>统计区间</span><input v-model="csvPeriod" /></label
                ><label class="field"
                  ><span>选取 CSV 数据行（从第 1 行数据算起）</span
                  ><select v-model="csvRow">
                    <option v-for="n in csvData.total" :key="n" :value="n - 1">
                      第 {{ n }} 行数据
                    </option>
                  </select></label
                ><label
                  class="field"
                  v-for="(txt, k) in {
                    plays: '播放次数',
                    retain_3s: '3 秒留存',
                    completion: '完播率',
                    avg_watch_s: '平均观看秒数',
                    likes: '点赞',
                    comments: '评论',
                    shares: '分享',
                    saves: '收藏',
                  }"
                  :key="k"
                  ><span>{{ txt }}</span
                  ><select v-model="csvMapping[k]">
                    <option value="">未提供</option>
                    <option v-for="c in csvData.columns" :key="c">
                      {{ c }}
                    </option>
                  </select></label
                >
              </div>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th v-for="c in csvData.columns" :key="c">{{ c }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(r, i) in csvData.rows" :key="i">
                      <td v-for="c in csvData.columns" :key="c">{{ r[c] }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="hint">
                从 CSV
                中选取当前成片与统计窗口对应的一行，不混加多日或多条视频。比例填写
                0–1 或带 %。缺失显示未提供，不作为 0。
              </div>
              <button class="accent" @click="commitCSV">确认映射并导入</button>
            </section>
            <section v-if="commentImport" class="panel">
              <div class="panel-title"><h2>评论字段映射</h2></div>
              <div class="form-grid">
                <label class="field"
                  ><span>评论文字列</span
                  ><select v-model="commentTextColumn">
                    <option v-for="c in commentColumns" :key="c">
                      {{ c }}
                    </option>
                  </select></label
                ><label class="field"
                  ><span>点赞列（可空）</span
                  ><select v-model="commentLikesColumn">
                    <option value="">未提供</option>
                    <option v-for="c in commentColumns" :key="c">
                      {{ c }}
                    </option>
                  </select></label
                >
              </div>
              <p class="note">其他列包括昵称、头像均不导入。</p>
              <button class="primary" @click="commitComments">
                确认导入评论
              </button>
            </section>
            <div class="metric-cards">
              <div
                class="metric"
                v-for="(txt, k) in {
                  plays: '播放次数',
                  retain_3s: '3 秒留存',
                  completion: '完播率',
                  avg_watch_s: '平均观看',
                  interaction: '互动率',
                }"
                :key="k"
              >
                <span>{{ txt }}</span
                ><strong>{{
                  !metrics
                    ? "待导入"
                    : k === "interaction"
                      ? metrics.data.plays &&
                        ["likes", "comments", "shares", "saves"].every(
                          (x) => metrics.data[x] !== null,
                        )
                        ? (
                            ((metrics.data.likes +
                              metrics.data.comments +
                              metrics.data.shares +
                              metrics.data.saves) /
                              metrics.data.plays) *
                            100
                          ).toFixed(1) + "%"
                        : "无法计算"
                      : metrics.data[k] === null
                        ? "未提供"
                        : ["retain_3s", "completion"].includes(k)
                          ? (metrics.data[k] * 100).toFixed(1) + "%"
                          : metrics.data[k] + (k === "avg_watch_s" ? "s" : "")
                }}</strong>
              </div>
            </div>
            <div class="two-col">
              <div>
                <section class="panel">
                  <div class="panel-title">
                    <h2>观众留存与镜头对照</h2>
                    <button class="text-btn push-right" @click="retentionForm">
                      <Plus :size="15" />登记留存点
                    </button>
                  </div>
                  <RetentionChart
                    v-if="points.length"
                    :points="points"
                    :shots="shotList"
                  />
                  <div v-else class="empty">
                    <ChartNoAxesCombined :size="36" />
                    <p>
                      没有留存采样点，暂不生成曲线。<br />后台未提供逐秒数据时，可手录几个真实采样点。
                    </p>
                  </div>
                  <div class="shot-intervals">
                    <span v-for="sh in shotList" :key="sh.id"
                      >{{ sh.start }}–{{ sh.end }}s <b>{{ sh.name }}</b></span
                    >
                  </div>
                </section>
                <section class="panel">
                  <div class="panel-title">
                    <h2>评论共鸣</h2>
                    <button class="text-btn push-right" @click="commentForm">
                      手录评论</button
                    ><button class="text-btn" @click="screenshotForm">
                      截图识别</button
                    ><button class="text-btn" @click="importComments">
                      导入评论 CSV</button
                    ><button
                      class="text-btn"
                      @click="
                        askAI('comment_tags', { comments: own('evidence') })
                      "
                    >
                      AI 标签建议
                    </button>
                  </div>
                  <blockquote v-for="e in own('evidence')" :key="e.id">
                    <MessageSquare :size="17" />
                    <div>
                      {{ e.data.text
                      }}<small
                        >{{ e.data.likes }} 赞 · {{ e.data.source }} ·
                        {{ e.data.tags?.join(" / ") }}</small
                      >
                    </div>
                  </blockquote>
                  <div v-if="!own('evidence').length" class="empty small">
                    尚未录入评论
                  </div>
                </section>
              </div>
              <aside>
                <section class="panel">
                  <div class="panel-title">
                    <h2>制作投入</h2>
                    <button class="text-btn push-right" @click="nav('costs')">
                      查看明细
                    </button>
                  </div>
                  <dl class="definition">
                    <dt>本片已记花费</dt>
                    <dd>{{ yuan(spent(projectId)) }}</dd>
                    <dt>生成尝试</dt>
                    <dd>{{ own("generation_record").length }} 次导出</dd>
                    <dt>已选用镜头</dt>
                    <dd>{{ selectedCount }} 镜</dd>
                    <dt>LLM 费用</dt>
                    <dd>
                      {{
                        yuan(
                          own("cost_entry")
                            .filter((x) => x.name === "LLM")
                            .reduce((a, x) => a + x.amount_fen / 100, 0),
                        )
                      }}<small
                        v-if="own('cost_entry').some((x) => x.data.unpriced)"
                        >含待核价条目，见流水</small
                      >
                    </dd>
                  </dl>
                </section>
                <section class="panel">
                  <div class="panel-title">
                    <h2>复盘判断</h2>
                    <button
                      class="text-btn push-right"
                      @click="
                        askAI('retro', {
                          metrics: metrics?.data,
                          retention: points.map((x) => x.data),
                        })
                      "
                    >
                      <Sparkles :size="14" />AI 建议
                    </button>
                  </div>
                  <label
                    class="field"
                    v-for="(txt, k) in {
                      observation: '观察',
                      hypothesis: '假设',
                      evidence: '依据',
                    }"
                    :key="k"
                    ><span>{{ txt }}</span
                    ><textarea v-model="retroForm[k]" rows="2" /></label
                  ><select v-model="retroForm.status" class="full-width">
                    <option>待验证</option>
                    <option>已验证</option>
                    <option>已否定</option>
                  </select>
                  <div class="hint">
                    相关性不等于因果，单条视频不能证明爆款概率。
                  </div>
                  <h3>下一条，只改一个变量</h3>
                  <label
                    class="field"
                    v-for="(txt, k) in {
                      exp_goal: '验证目标',
                      exp_keep: '保持不变',
                      exp_change: '尝试修改',
                    }"
                    :key="k"
                    ><span>{{ txt }}</span
                    ><textarea v-model="retroForm[k]" rows="2" /></label
                  ><button class="primary full-width" @click="nextProject">
                    <Plus :size="15" />生成下一条简报草稿
                  </button>
                </section>
              </aside>
            </div>
            <div class="action-bar">
              <button @click="nav('delivery')">
                <ArrowLeft :size="16" />成片与交付</button
              ><button class="push-right" @click="saveRetro">
                保存复盘记录</button
              ><button
                class="accent"
                @click="saveRetro().then(() => confirmStage(7))"
              >
                确认复盘，完成本项目<Check :size="16" />
              </button></div
          ></template>

          <template v-if="page === 'settings'"
            ><div class="section-tabs">
              <button
                v-for="(txt, k) in {
                  profiles: '模型档案',
                  llm: 'LLM 配置',
                  templates: '提示词模板',
                  backup: '备份与恢复',
                }"
                :key="k"
                :class="{ active: modelPanel === k }"
                @click="modelPanel = k"
              >
                {{ txt }}
              </button>
            </div>
            <section class="panel" v-if="modelPanel === 'profiles'">
              <div class="panel-title">
                <h2>图片与视频模型档案</h2>
                <button class="accent push-right" @click="modelForm()">
                  <Plus :size="16" />新增模型档案
                </button>
              </div>
              <p class="muted">
                这里记录官网使用参数，不连接生成接口。只有填写核对日期、能力范围和单价后，才能导出有效提交包。
              </p>
              <div class="profile-grid">
                <article
                  v-for="m in list('model_profile')"
                  :key="m.id"
                  class="model-profile"
                >
                  <div class="panel-title">
                    <span class="stat-icon"><Layers :size="23" /></span>
                    <h2>{{ m.name }}</h2>
                    <span
                      class="pill push-right"
                      :class="{ amber: !m.data.verified_at }"
                      >{{ m.data.verified_at ? "已核对" : "未核对" }}</span
                    >
                  </div>
                  <dl class="definition">
                    <dt>实际版本</dt>
                    <dd>{{ m.data.version || "待填写" }}</dd>
                    <dt>时长档位</dt>
                    <dd>{{ m.data.durations?.join(" / ") || "待核对" }}</dd>
                    <dt>图片 / 音频</dt>
                    <dd>
                      {{ m.data.max_ref_images }} / {{ m.data.max_audio }}
                    </dd>
                    <dt>画幅</dt>
                    <dd>{{ m.data.ratios?.join(" / ") || "待核对" }}</dd>
                    <dt>单价</dt>
                    <dd>
                      {{ m.data.credit_price ?? "—" }} 积分 ×
                      {{ m.data.credit_to_cny ?? "—" }} 元
                    </dd>
                    <dt>核对日期</dt>
                    <dd>{{ m.data.verified_at || "尚未登记" }}</dd>
                  </dl>
                  <div class="row-actions">
                    <button class="primary" @click="modelForm(m)">
                      编辑与核对</button
                    ><a
                      :href="m.data.site_url"
                      target="_blank"
                      rel="noopener noreferrer"
                      >打开官网<ExternalLink :size="12"
                    /></a>
                  </div>
                </article>
              </div>
            </section>
            <template v-if="modelPanel === 'llm'"
              ><div class="two-equal">
                <section
                  class="panel"
                  v-for="(form, i) in [llmText, llmVision]"
                  :key="i"
                >
                  <div class="panel-title">
                    <h2>{{ i ? "多模态 LLM" : "文本 LLM" }}</h2>
                    <span class="pill push-right">{{
                      form.has_key ? "已保存密钥" : "未配置"
                    }}</span>
                  </div>
                  <p class="note">
                    {{
                      i
                        ? "用于截图识别，需支持图片输入的模型。"
                        : "用于方向归纳、剧情、分镜、提示词与复盘建议。"
                    }}
                  </p>
                  <label class="field"
                    ><span>协议</span
                    ><select v-model="form.provider">
                      <option value="openai">OpenAI 兼容协议</option>
                      <option value="anthropic">Anthropic</option>
                    </select></label
                  ><label class="field"
                    ><span>API Base URL</span
                    ><input
                      v-model="form.base_url"
                      type="url"
                      placeholder="https://你的提供商/v1" /></label
                  ><label class="field"
                    ><span>模型名称</span
                    ><input
                      v-model="form.model"
                      placeholder="填写提供商的实际模型 ID" /></label
                  ><label class="field"
                    ><span>API Key</span
                    ><input
                      v-model="form.api_key"
                      type="password"
                      autocomplete="off"
                      :placeholder="
                        form.has_key
                          ? '已保存；留空保持原密钥'
                          : '仅保存在本机加密存储'
                      "
                  /></label>
                  <div class="form-grid">
                    <label class="field"
                      ><span>输入每百万 token 单价（元）</span
                      ><input
                        v-model.number="form.input_price_per_million"
                        type="number"
                        min="0" /></label
                    ><label class="field"
                      ><span>输出每百万 token 单价（元）</span
                      ><input
                        v-model.number="form.output_price_per_million"
                        type="number"
                        min="0"
                    /></label>
                  </div>
                  <button
                    class="primary full-width"
                    @click="saveLLM(i ? 'llm_vision' : 'llm_text')"
                  >
                    保存{{ i ? "多模态" : "文本" }}配置
                  </button>
                  <p class="note">
                    填单价后按实际 token
                    估算入账；没有单价的调用记为待核价，后续可人工对账。
                  </p>
                </section>
              </div>
              <section class="panel">
                <div class="panel-title">
                  <h2>AI 调用记录</h2>
                  <span class="muted">每次任务保留输出、校验状态和费用</span>
                </div>
                <div
                  v-if="!list('task').filter((x) => x.name === 'llm').length"
                  class="empty small"
                >
                  还没有 AI 调用。
                </div>
                <div
                  v-for="t in list('task').filter((x) => x.name === 'llm')"
                  :key="t.id"
                  class="record-row"
                >
                  <b>{{ t.data.purpose }}</b
                  ><span>{{ label(t.status) }} · {{ date(t.created_at) }}</span>
                  <p class="error-text">{{ t.data.error }}</p>
                  <details v-if="t.data.result">
                    <summary>查看 AI 建议</summary>
                    <pre>{{ JSON.stringify(t.data.result, null, 2) }}</pre>
                  </details>
                </div>
              </section></template
            >
            <section v-if="modelPanel === 'templates'" class="panel">
              <div class="panel-title">
                <h2>创作提示词模板</h2>
                <span class="pill">版本管理</span>
              </div>
              <div
                v-for="t in list('prompt_template').filter(
                  (x) => x.status === 'active',
                )"
                :key="t.id"
                class="template-row"
              >
                <FileText :size="22" />
                <div>
                  <h3>{{ t.data.label }}</h3>
                  <small>{{ t.name }} · v{{ t.version }}</small>
                  <p>{{ t.data.body.slice(0, 100) }}…</p>
                </div>
                <button @click="templateForm(t)">编辑新版本</button>
              </div>
            </section>
            <section v-if="modelPanel === 'backup'" class="panel backup-panel">
              <HardDrive :size="48" />
              <h2>让每一次创作留在你手里</h2>
              <p>
                数据库与素材保存在本地目录。运行期间每日自动备份，保留最近 7
                份；也可随时下载完整备份。
              </p>
              <div class="row-actions">
                <button class="primary" @click="makeBackup">
                  <Download :size="17" />下载完整备份</button
                ><button @click="restoreForm">
                  <Upload :size="17" />从 ZIP 恢复
                </button>
              </div>
              <div class="hint">
                API
                主密钥存于系统凭据管理器，不随备份导出。在其他电脑恢复后需重新填写
                API Key。
              </div>
            </section></template
          >

          <template v-if="page === 'compare'">
            <section class="panel">
              <div class="panel-title">
                <h2>发布版本指标对照</h2>
                <span class="pill amber"
                  >按平台与统计窗口对照，不跨口径排名</span
                ><button class="text-btn push-right" @click="nav('projects')">
                  返回项目
                </button>
              </div>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>项目 / 成片</th>
                      <th>平台</th>
                      <th>统计窗口</th>
                      <th>播放</th>
                      <th>3 秒留存</th>
                      <th>完播率</th>
                      <th>平均观看</th>
                      <th>下一条实验</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="m in list('metric_snapshot').filter(
                        (x) =>
                          !search ||
                          byId('project', x.project_id)?.name.includes(search),
                      )"
                      :key="m.id"
                    >
                      <td>
                        <b>{{
                          byId("project", m.project_id)?.name || "历史项目"
                        }}</b
                        ><small>发布 {{ m.parent_id?.slice(0, 8) }}</small>
                      </td>
                      <td>{{ byId("release", m.parent_id)?.name }}</td>
                      <td>{{ m.data.period }}</td>
                      <td>{{ m.data.plays ?? "未提供" }}</td>
                      <td>
                        {{
                          m.data.retain_3s == null
                            ? "未提供"
                            : (m.data.retain_3s * 100).toFixed(1) + "%"
                        }}
                      </td>
                      <td>
                        {{
                          m.data.completion == null
                            ? "未提供"
                            : (m.data.completion * 100).toFixed(1) + "%"
                        }}
                      </td>
                      <td>{{ m.data.avg_watch_s ?? "未提供" }}</td>
                      <td>
                        {{
                          list("retro", m.project_id).at(-1)?.data.exp_change ||
                          "待复盘"
                        }}
                      </td>
                      <td>
                        <button
                          @click="
                            nav('retro', m.project_id);
                            metricSnapshotId = m.id;
                            releaseId = m.parent_id;
                          "
                        >
                          查看复盘
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-if="!list('metric_snapshot').length" class="empty large">
                <ChartNoAxesCombined :size="36" />
                <p>还没有真实指标。先在项目复盘中导入平台 CSV。</p>
              </div>
            </section>
            <section class="panel">
              <div class="panel-title"><h2>单变量实验记录</h2></div>
              <table>
                <thead>
                  <tr>
                    <th>项目</th>
                    <th>验证目标</th>
                    <th>保持不变</th>
                    <th>尝试修改</th>
                    <th>结论状态</th>
                    <th>下一条</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="r in list('retro')" :key="r.id">
                    <td>
                      {{ byId("project", r.project_id)?.name || "历史项目" }}
                    </td>
                    <td>{{ r.data.exp_goal }}</td>
                    <td>{{ r.data.exp_keep }}</td>
                    <td>{{ r.data.exp_change }}</td>
                    <td>
                      <span class="pill">{{ r.status }}</span>
                    </td>
                    <td>
                      {{
                        byId("project", r.data.next_project_id)?.name ||
                        "未创建"
                      }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </section>
          </template>
          <template v-if="page === 'costs'"
            ><div class="two-col">
              <section class="panel">
                <div class="panel-title">
                  <h2>费用流水</h2>
                  <button class="text-btn push-right" @click="costForm()">
                    <Plus :size="15" />手动记账</button
                  ><a class="button" href="/api/costs/export"
                    ><Download :size="15" />导出 CSV</a
                  >
                </div>
                <div class="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>日期</th>
                        <th>项目</th>
                        <th>分类</th>
                        <th>积分</th>
                        <th>人民币</th>
                        <th>账单状态</th>
                        <th>核对</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="c in list('cost_entry').sort((a, b) =>
                          b.created_at.localeCompare(a.created_at),
                        )"
                        :key="c.id"
                      >
                        <td>{{ date(c.created_at) }}</td>
                        <td>
                          {{ byId("project", c.project_id)?.name || "全局" }}
                        </td>
                        <td>{{ c.name }}</td>
                        <td>{{ c.data.credits || 0 }}</td>
                        <td>
                          {{
                            c.data.unpriced
                              ? "待核价"
                              : yuan(c.amount_fen / 100)
                          }}
                        </td>
                        <td>
                          <span
                            class="pill"
                            :class="{
                              amber: c.data.unpriced || c.data.estimated,
                            }"
                            >{{
                              c.data.unpriced
                                ? "待核价"
                                : c.data.estimated
                                  ? "按 token 估算"
                                  : "已登记"
                            }}</span
                          >
                        </td>
                        <td>
                          <button class="text-btn" @click="costForm(c)">
                            核对账单
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-if="!list('cost_entry').length" class="empty large">
                  <Wallet :size="36" />
                  <p>还没有费用。回传资产、候选时可记账，也可在此补录。</p>
                </div>
              </section>
              <aside class="panel">
                <h2>月度预算</h2>
                <label class="field"
                  ><span>预算上限（人民币）</span
                  ><input
                    v-model.number="budget.monthly_cap"
                    type="number"
                    min="0" /></label
                ><label class="check-field"
                  ><input
                    type="checkbox"
                    v-model="budget.pause"
                  />达到上限暂停导出提交包</label
                >
                <div class="budget-amounts">
                  <div>
                    <small>本月已记</small
                    ><strong>{{ yuan(monthlySpend) }}</strong>
                  </div>
                  <div>
                    <small>全部累计</small
                    ><strong>{{ yuan(db.total_spend) }}</strong>
                  </div>
                </div>
                <button
                  class="primary full-width"
                  @click="
                    act(
                      () => api('/settings/budget', 'POST', budget),
                      '月度预算已保存',
                    )
                  "
                >
                  保存预算
                </button>
                <div class="hint">
                  <Info
                    :size="16"
                  />预算约束平台的导出操作。官网费用发生后，需你及时登记；已导出的包不会撤回。
                </div>
              </aside>
            </div></template
          >
        </template>
        <footer class="page-footer">
          <PawPrint :size="14" /><span>猫片工场 · 让灵感成为有迹可循的作品</span
          ><span class="push-right"
            ><span class="live-dot" /> 文件与数据保存在本机</span
          >
        </footer>
      </main>
    </div>
    <FormModal :model="modal" @close="modal = null" />
    <div v-if="busy" class="busy-indicator">
      <RefreshCw :size="15" class="spin" />正在处理…
    </div>
    <Teleport to="body"
      ><div v-if="showAI" class="modal-shade">
        <section class="modal ai-modal">
          <header>
            <h2><Sparkles :size="20" />AI 建议 · 待人工确认</h2>
            <button @click="showAI = false">关闭</button>
          </header>
          <p class="note">
            采用后保存为可编辑草稿，仍需完成当前阶段的人工检查。
          </p>
          <textarea
            class="ai-result-editor"
            v-model="aiDraft"
            rows="16"
            aria-label="校对 AI 建议 JSON"
          />
          <footer>
            <button @click="copy(JSON.stringify(aiResult.result, null, 2))">
              复制结果</button
            ><button class="primary" @click="adoptAI">采用为草稿</button>
          </footer>
        </section>
      </div></Teleport
    >
  </div>
</template>
