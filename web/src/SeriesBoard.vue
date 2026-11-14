<script setup>
import { ref, computed, watch } from "vue";
import {
  Clapperboard,
  ListChecks,
  Clock,
  ShoppingBag,
  Plus,
  ExternalLink,
  ArrowRight,
  Download,
} from "lucide-vue-next";
import { api, act, save, list, nav, busy, notify, yuan, clone } from "./studio";

const templates = ref([]),
  board = ref(null),
  error = ref(""),
  tab = ref("episodes"),
  openId = ref("");
const channel = ref({ subscribers: 0, shorts_views_90d: 0 });
const checks = ref({}),
  work = ref({ hours: "", note: "" }),
  publishUrl = ref("");
const productDraft = ref({
  name: "",
  category: "",
  platform: "Shopify",
  url: "",
  commission_pct: "",
});

const series = computed(() => list("series")[0]);
const statusText = { draft: "制作中", ready: "可发布", published: "已发布" };
const statusClass = { draft: "draft", ready: "pending", published: "complete" };
const subLabel = (key) =>
  series.value?.data.subseries.find((x) => x.key === key)?.label || key;
const threadName = (key) =>
  series.value?.data.threads.find((x) => x.key === key)?.name || key;
const weeks = computed(() => board.value?.weeks || []);
const inWeek = (n) => board.value.episodes.filter((x) => x.week === n);
const open = computed(() =>
  board.value?.episodes.find((x) => x.id === openId.value),
);
const characters = computed(() =>
  list("character")
    .filter((x) => x.parent_id === series.value?.id)
    .sort((a, b) => a.seq - b.seq),
);
const scenes = computed(() =>
  list("scene")
    .filter((x) => x.parent_id === series.value?.id)
    .sort((a, b) => a.seq - b.seq),
);
const products = computed(() =>
  list("product").filter((x) => x.parent_id === series.value?.id),
);
const pct = (p) => Math.round(p.ratio * 100) + "%";
const num = (n) => Number(n || 0).toLocaleString("zh-CN");

async function load() {
  error.value = "";
  try {
    if (!series.value) {
      templates.value = await api("/series/templates");
      board.value = null;
      return;
    }
    board.value = await api("/series/" + series.value.id + "/board");
    const c = board.value.series.data.channel || {};
    channel.value = {
      subscribers: c.subscribers || 0,
      shorts_views_90d: c.shorts_views_90d || 0,
    };
  } catch (e) {
    error.value = e.message;
  }
}
// The shared state may arrive after this page mounts; reload when the series appears.
watch(() => series.value?.id, load, { immediate: true });
const run = async (fn, message) => {
  const r = await act(fn, message);
  await load();
  return r;
};

const importSeason = (key) =>
  run(() => api("/series/import", "POST", { key }), "首季已导入");
function toggle(ep) {
  openId.value = openId.value === ep.id ? "" : ep.id;
  checks.value = clone(ep.checks);
  work.value = { hours: "", note: "" };
  publishUrl.value = ep.youtube_url || "";
}
async function openProject(ep) {
  const p = ep.project_id
    ? { id: ep.project_id }
    : await run(
        () => api("/series/episodes/" + ep.id + "/project", "POST"),
        "已按" + ep.tier + " 档模板创建制作项目",
      );
  if (p) nav("brief", p.id);
}
const record = (ep) =>
  list("episode").find((x) => x.id === ep.id);
async function patchEpisode(ep, changes, message) {
  const current = record(ep);
  await run(
    () =>
      save(
        "episode",
        { revision: current.revision, data: { ...current.data, ...changes } },
        ep.id,
      ),
    message,
  );
}
const setEnding = (ep, value) =>
  patchEpisode(ep, { ending_type: value }, "结局类型已更新，需重新做发布前检查");
function toggleProduct(ep, id) {
  const ids = ep.product_ids.includes(id)
    ? ep.product_ids.filter((x) => x !== id)
    : [...ep.product_ids, id];
  return patchEpisode(ep, { product_ids: ids }, "出镜商品已更新");
}
const saveChecks = (ep) =>
  run(
    () =>
      api("/series/episodes/" + ep.id + "/checks", "POST", {
        checks: checks.value,
      }),
    "检查结果已保存",
  );
async function addWork(ep) {
  const r = await run(
    () =>
      api("/series/episodes/" + ep.id + "/worklog", "POST", {
        hours: work.value.hours,
        note: work.value.note,
      }),
    "工时已记录",
  );
  if (r) work.value = { hours: "", note: "" };
}
const publish = (ep) =>
  run(
    () =>
      api("/series/episodes/" + ep.id + "/publish", "POST", {
        youtube_url: publishUrl.value,
      }),
    "已登记发布",
  );
const saveChannel = () =>
  run(
    () =>
      api("/series/" + series.value.id + "/channel", "POST", channel.value),
    "频道数据已更新",
  );
async function addProduct() {
  const d = productDraft.value;
  if (!d.name.trim()) return notify("请填写商品名称", "warning");
  const r = await run(
    () =>
      save("product", {
        parent_id: series.value.id,
        name: d.name.trim().slice(0, 60),
        data: {
          category: d.category,
          platform: d.platform,
          url: d.url.trim(),
          commission_pct: d.commission_pct === "" ? null : Number(d.commission_pct),
        },
      }),
    "商品已加入选品库",
  );
  if (r)
    productDraft.value = {
      name: "",
      category: "",
      platform: "Shopify",
      url: "",
      commission_pct: "",
    };
}
const productEpisodes = (id) =>
  board.value.episodes
    .filter((x) => x.product_ids.includes(id))
    .map((x) => "EP" + x.no)
    .join("、") || "未安排";
</script>

<template>
  <div class="series-board">
    <p v-if="error" class="pw-warning">{{ error }}</p>

    <section v-if="!series" class="panel">
      <div class="panel-title"><h2>还没有系列</h2></div>
      <p class="muted">
        系列把多集视频组织在一起：固定角色和场景、每集的结局类型、跨集线、出镜商品、工时。导入后不会自动通过任何审核，每集仍走七步制片。
      </p>
      <div v-for="t in templates" :key="t.key" class="sb-template">
        <div>
          <b>{{ t.name }} · 第 {{ t.season }} 季</b>
          <p class="muted">
            {{ t.positioning }}｜{{ t.episodes }} 集｜建议
            {{ t.start_date }} 开播｜角色：{{ t.characters.join("、") }}
          </p>
        </div>
        <button class="accent" :disabled="busy" @click="importSeason(t.key)">
          <Download :size="16" />导入首季
        </button>
      </div>
    </section>

    <template v-if="series && board">
      <div class="stats-row">
        <div class="stat">
          <div class="stat-icon"><Clapperboard :size="20" /></div>
          <div>
            <p>已发布 / 总集数</p>
            <strong
              >{{ board.summary.by_status.published || 0 }} /
              {{ board.summary.total }}</strong
            >
          </div>
        </div>
        <div class="stat">
          <div class="stat-icon amber"><ListChecks :size="20" /></div>
          <div>
            <p>通过发布前检查</p>
            <strong>{{
              (board.summary.by_status.ready || 0) +
              (board.summary.by_status.published || 0)
            }}</strong>
          </div>
        </div>
        <div class="stat">
          <div class="stat-icon"><Clock :size="20" /></div>
          <div>
            <p>累计工时（小时）</p>
            <strong>{{ board.summary.hours }}</strong>
          </div>
        </div>
        <div class="stat">
          <div class="stat-icon amber"><ShoppingBag :size="20" /></div>
          <div>
            <p>累计生成费用</p>
            <strong>{{ yuan(board.summary.cost_cny) }}</strong>
          </div>
        </div>
      </div>

      <section class="panel sb-eligibility">
        <div class="panel-title">
          <h2>带货与分成门槛进度</h2>
          <span class="muted push-right"
            >门槛口径 {{ board.eligibility.as_of }}｜{{
              board.eligibility.note
            }}</span
          >
        </div>
        <div class="sb-elig-grid">
          <div v-for="t in board.eligibility.tiers" :key="t.key">
            <b>{{ t.label }}</b>
            <span class="status" :class="t.met ? 'complete' : 'draft'">{{
              t.met ? "已达到" : "未达到"
            }}</span>
            <p class="muted">
              订阅 {{ num(t.subscribers.current) }} /
              {{ num(t.subscribers.target) }}（{{ pct(t.subscribers) }}）
            </p>
            <div class="progress-track">
              <div :style="{ width: pct(t.subscribers) }"></div>
            </div>
            <p class="muted">
              90 天 Shorts 有效播放 {{ num(t.shorts_views_90d.current) }} /
              {{ num(t.shorts_views_90d.target) }}（{{
                pct(t.shorts_views_90d)
              }}）
              <template v-if="t.later_target"
                >｜2027-02-01 起新申请为 {{ num(t.later_target) }}</template
              >
            </p>
            <div class="progress-track">
              <div :style="{ width: pct(t.shorts_views_90d) }"></div>
            </div>
          </div>
          <form class="sb-channel" @submit.prevent="saveChannel">
            <label
              >当前订阅数<input
                v-model.number="channel.subscribers"
                type="number"
                min="0"
            /></label>
            <label
              >近 90 天 Shorts 有效播放<input
                v-model.number="channel.shorts_views_90d"
                type="number"
                min="0"
            /></label>
            <button :disabled="busy">更新频道数据</button>
            <p class="muted">数字从 YouTube Studio 手动抄录。</p>
          </form>
        </div>
      </section>

      <div class="section-tabs">
        <button :class="{ active: tab === 'episodes' }" @click="tab = 'episodes'">
          分集台账
        </button>
        <button :class="{ active: tab === 'bible' }" @click="tab = 'bible'">
          角色与场景
        </button>
        <button :class="{ active: tab === 'threads' }" @click="tab = 'threads'">
          跨集线与周产能
        </button>
        <button :class="{ active: tab === 'products' }" @click="tab = 'products'">
          选品库 <span class="muted">{{ products.length }}</span>
        </button>
        <span
          v-if="board.summary.ending_conflicts.length"
          class="warning-text push-right"
          >结局类型与前两集重复：第
          {{ board.summary.ending_conflicts.join("、") }} 集</span
        >
      </div>

      <template v-if="tab === 'episodes'">
        <section v-for="w in weeks" :key="w.week" class="panel">
          <div class="panel-title">
            <h2>第 {{ w.week }} 周</h2>
            <span class="muted push-right"
              >计划 {{ w.planned_hours }} 小时｜实际
              {{ w.actual_hours }} 小时｜预算 {{ w.budget_hours }} 小时｜可发布
              {{ w.ready }} / {{ w.episodes }}</span
            >
            <span v-if="w.over_budget" class="status failed">超出周预算</span>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>集</th>
                  <th>发布日</th>
                  <th>子系列</th>
                  <th>档</th>
                  <th>标题</th>
                  <th>结局类型</th>
                  <th>检查</th>
                  <th>工时</th>
                  <th>状态</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <template v-for="ep in inWeek(w.week)" :key="ep.id">
                  <tr :class="{ 'sb-open': openId === ep.id }">
                    <td>{{ ep.no }}</td>
                    <td>{{ ep.publish_date?.slice(5) }}</td>
                    <td>{{ subLabel(ep.subseries) }}</td>
                    <td>
                      <span class="status" :class="ep.tier === 'A' ? 'pending' : 'draft'">{{ ep.tier }}</span>
                    </td>
                    <td>
                      <b>{{ ep.name }}</b>
                      <span v-for="t in ep.threads" :key="t" class="status">{{ threadName(t) }}</span>
                    </td>
                    <td>
                      <select
                        :value="ep.ending_type"
                        :disabled="busy || ep.status === 'published'"
                        :class="{ 'sb-conflict': ep.ending_conflict }"
                        :aria-label="'第 ' + ep.no + ' 集结局类型'"
                        @change="setEnding(ep, $event.target.value)"
                      >
                        <option v-for="t in series.data.ending_types" :key="t">{{ t }}</option>
                      </select>
                    </td>
                    <td>{{ ep.checks_done }} / 5</td>
                    <td>{{ ep.hours }} / {{ ep.planned_hours }}</td>
                    <td>
                      <span class="status" :class="statusClass[ep.status]">{{ statusText[ep.status] }}</span>
                    </td>
                    <td class="row-actions">
                      <button class="text-btn" @click="toggle(ep)">
                        {{ openId === ep.id ? "收起" : "台账" }}
                      </button>
                      <button class="text-btn" :disabled="busy" @click="openProject(ep)">
                        <template v-if="ep.project_id">进入制作<ArrowRight :size="14" /></template>
                        <template v-else><Plus :size="14" />建项目</template>
                      </button>
                    </td>
                  </tr>
                  <tr v-if="openId === ep.id" class="sb-detail">
                    <td colspan="10">
                      <p>{{ ep.logline }}</p>
                      <p class="muted">
                        建议出镜品类：{{ ep.product_categories.join("、") }}｜生成费用
                        {{ yuan(ep.cost_cny) }}
                      </p>
                      <div class="sb-detail-grid">
                        <div>
                          <b>发布前检查</b>
                          <label v-for="c in series.data.checks" :key="c.key" class="sb-check">
                            <input
                              v-model="checks[c.key]"
                              type="checkbox"
                              :disabled="ep.status === 'published'"
                            />{{ c.label }}
                          </label>
                          <button :disabled="busy || ep.status === 'published'" @click="saveChecks(ep)">
                            保存检查结果
                          </button>
                        </div>
                        <div>
                          <b>记工时</b>
                          <label
                            >小时<input v-model="work.hours" type="number" min="0.1" max="24" step="0.1"
                          /></label>
                          <label
                            >说明<input v-model="work.note" maxlength="200" placeholder="如：生图返工两次"
                          /></label>
                          <button :disabled="busy || !work.hours" @click="addWork(ep)">记录</button>
                          <b class="mt">出镜商品</b>
                          <p v-if="!products.length" class="muted">选品库为空，先到「选品库」添加。</p>
                          <label v-for="p in products" :key="p.id" class="sb-check">
                            <input
                              type="checkbox"
                              :checked="ep.product_ids.includes(p.id)"
                              :disabled="busy"
                              @change="toggleProduct(ep, p.id)"
                            />{{ p.name }}
                          </label>
                        </div>
                        <div>
                          <b>登记发布</b>
                          <label
                            >YouTube 链接<input
                              v-model="publishUrl"
                              placeholder="https://www.youtube.com/shorts/…"
                          /></label>
                          <button :disabled="busy || ep.status === 'draft'" @click="publish(ep)">
                            {{ ep.status === "published" ? "更新链接" : "登记为已发布" }}
                          </button>
                          <p v-if="ep.status === 'draft'" class="muted">五项检查全部通过后才能登记。</p>
                          <a v-if="ep.youtube_url" class="button" :href="ep.youtube_url" target="_blank" rel="noopener"
                            ><ExternalLink :size="14" />打开视频</a
                          >
                        </div>
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <template v-if="tab === 'bible'">
        <section class="panel">
          <div class="panel-title"><h2>角色设定</h2></div>
          <div class="sb-cards">
            <div v-for="c in characters" :key="c.id" class="sb-card">
              <b>{{ c.name }}（{{ c.data.cn }}）</b>
              <span class="status">{{ c.data.role }}</span>
              <span v-if="c.data.voiced" class="status pending">配音</span>
              <dl>
                <dt>外形</dt>
                <dd>{{ c.data.look }}</dd>
                <template v-if="c.data.outfit"><dt>服装</dt><dd>{{ c.data.outfit }}</dd></template>
                <dt>性格</dt>
                <dd>{{ c.data.personality }}</dd>
                <template v-if="c.data.voice"><dt>说话方式</dt><dd>{{ c.data.voice }}</dd></template>
                <template v-if="c.data.gags"><dt>固定梗</dt><dd>{{ c.data.gags }}</dd></template>
                <template v-if="c.data.never"><dt>不会做的事</dt><dd>{{ c.data.never }}</dd></template>
              </dl>
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-title"><h2>固定场景</h2></div>
          <div class="chip-row">
            <span v-for="x in scenes" :key="x.id" class="status">{{ x.data.code }} · {{ x.name }}</span>
          </div>
          <p class="muted">
            角色身份母图和场景图仍在「数字资产」里制作和定稿；新建分集项目时，分镜生图词会自动带上主角的外形和服装描述。
          </p>
        </section>
      </template>

      <template v-if="tab === 'threads'">
        <section class="panel">
          <div class="panel-title"><h2>跨集线</h2></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>线</th><th>说明</th><th>涉及分集</th></tr></thead>
              <tbody>
                <tr v-for="t in board.threads" :key="t.key">
                  <td><b>{{ t.name }}</b></td>
                  <td>{{ t.note }}</td>
                  <td>
                    <span v-for="e in t.episodes" :key="e.no" class="status" :class="statusClass[e.status]"
                      >EP{{ e.no }} {{ statusText[e.status] }}</span
                    >
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="panel">
          <div class="panel-title"><h2>周产能</h2></div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>周</th><th>集数</th><th>计划工时</th><th>实际工时</th><th>周预算</th><th>可发布</th><th>已发布</th></tr>
              </thead>
              <tbody>
                <tr v-for="w in weeks" :key="w.week">
                  <td>第 {{ w.week }} 周</td>
                  <td>{{ w.episodes }}</td>
                  <td>{{ w.planned_hours }}</td>
                  <td :class="{ 'warning-text': w.over_budget }">{{ w.actual_hours }}</td>
                  <td>{{ w.budget_hours }}</td>
                  <td>{{ w.ready }}</td>
                  <td>{{ w.published }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <template v-if="tab === 'products'">
        <section class="panel">
          <div class="panel-title">
            <h2>选品库</h2>
            <span class="muted push-right"
              >尚未安排商品的分集：{{ board.summary.without_product.length }} 集</span
            >
          </div>
          <form class="sb-product-form" @submit.prevent="addProduct">
            <label>商品名称<input v-model="productDraft.name" maxlength="60" /></label>
            <label>品类<input v-model="productDraft.category" maxlength="30" placeholder="如：宿舍小家电" /></label>
            <label
              >来源平台<select v-model="productDraft.platform">
                <option>Shopify</option><option>Amazon</option><option>TikTok Shop</option><option>其他</option>
              </select></label
            >
            <label>商品链接<input v-model="productDraft.url" placeholder="https://" /></label>
            <label>佣金 %<input v-model="productDraft.commission_pct" type="number" min="0" max="100" step="0.1" /></label>
            <button class="accent" :disabled="busy"><Plus :size="16" />添加</button>
          </form>
          <div class="table-wrap">
            <table>
              <thead><tr><th>商品</th><th>品类</th><th>平台</th><th>佣金</th><th>出镜分集</th><th>链接</th></tr></thead>
              <tbody>
                <tr v-if="!products.length"><td colspan="6" class="muted">还没有商品。</td></tr>
                <tr v-for="p in products" :key="p.id">
                  <td><b>{{ p.name }}</b></td>
                  <td>{{ p.data.category }}</td>
                  <td>{{ p.data.platform }}</td>
                  <td>{{ p.data.commission_pct == null ? "未填" : p.data.commission_pct + "%" }}</td>
                  <td>{{ productEpisodes(p.id) }}</td>
                  <td>
                    <a v-if="p.data.url" :href="p.data.url" target="_blank" rel="noopener">打开</a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </template>
  </div>
</template>

<style scoped>
.series-board .panel {
  margin-bottom: 18px;
}
.sb-template {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px 16px;
  margin-top: 14px;
}
.sb-elig-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 260px;
  gap: 24px;
}
.sb-elig-grid .progress-track {
  margin: 6px 0 12px;
}
.sb-elig-grid .status {
  margin-left: 8px;
}
.sb-channel label,
.sb-detail label,
.sb-product-form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 8px;
}
.sb-channel input,
.sb-detail input:not([type="checkbox"]),
.sb-product-form input,
.sb-product-form select {
  border: 1px solid #d5ddd5;
  border-radius: 6px;
  padding: 7px 9px;
}
.series-board td .status {
  margin-left: 6px;
}
.series-board td select {
  border: 1px solid #d5ddd5;
  border-radius: 6px;
  padding: 5px 6px;
  background: #fff;
}
.series-board td select.sb-conflict {
  border-color: #bb6a4b;
  background: #f9e7e0;
}
tr.sb-open td {
  background: #f3f6ef;
}
tr.sb-detail td {
  background: #fafbf8;
  padding: 14px 18px 18px;
}
.sb-detail-grid {
  display: grid;
  grid-template-columns: 1.3fr 1fr 1fr;
  gap: 24px;
  margin-top: 12px;
}
.sb-detail-grid b {
  display: block;
  margin-bottom: 8px;
}
.sb-detail-grid b.mt {
  margin-top: 16px;
}
.sb-check {
  flex-direction: row !important;
  align-items: flex-start;
  gap: 8px !important;
  color: #2f483e !important;
}
.sb-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.sb-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px 16px;
}
.sb-card .status {
  margin-left: 8px;
}
.sb-card dl {
  display: grid;
  grid-template-columns: 84px 1fr;
  gap: 6px 10px;
  margin: 12px 0 0;
  font-size: 12px;
}
.sb-card dt {
  color: var(--muted);
}
.sb-card dd {
  margin: 0;
}
.sb-product-form {
  display: grid;
  grid-template-columns: 1.4fr 1fr 0.8fr 1.6fr 0.6fr auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 14px;
}
.sb-product-form button {
  margin-bottom: 8px;
}
@media (max-width: 1100px) {
  .sb-elig-grid,
  .sb-detail-grid,
  .sb-cards,
  .sb-product-form {
    grid-template-columns: 1fr;
  }
}
</style>
