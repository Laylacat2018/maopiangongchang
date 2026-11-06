<script setup>
import { ref, computed, onMounted, watch } from "vue";
import {
  Play,
  Copy,
  ArrowRight,
  CheckCheck,
  Upload,
  Clapperboard,
  BookOpen,
} from "lucide-vue-next";
import {
  api,
  act,
  save,
  upload,
  fileUrl,
  project,
  projectId,
  list,
  own,
  shotList,
  nav,
  busy,
  notify,
  yuan,
} from "./studio";

const sample = ref(null),
  error = ref(""),
  view = ref("example"),
  step = ref(1),
  exampleShot = ref(0),
  shotId = ref("");
const nonce = ref(crypto.randomUUID()),
  projectName = ref("今天没早八 · 我的新制作");
const draft = ref({}),
  checks = ref({}),
  packagePreview = ref(null);
const steps = [
  {
    name: "固定主角",
    model: "即梦 · 参考图生图 / 图像编辑",
    page: "assets",
    gate: "G1 人工选定角色",
    output: "身份母图、固定脸型 / 额纹 / 眼色 / 猫爪 / 性格。A版可复用。",
    check: "对照母图看脸、猫爪、毛纹、服装。身份或服装版本变化后重审。",
    tip: "先简化配饰和姿势；每镜引用同一身份母图。",
    prompt:
      "基于上传的身份母图保持同一只金渐层圆脸猫：M形额纹、琥珀眼、粉鼻、完整猫爪、米色睡衣。生成单幅角色参考图，温暖柔光，保留毛发质感，不增加人类手指、文字或额外肢体。",
  },
  {
    name: "生成脚本",
    model: "豆包 · 可用的文字 / 多模态模型",
    page: "script",
    gate: "G2 人工审故事",
    output: "一句话故事、目标、阻力、选择、反转、逐镜时长与字幕。",
    check: "是否解压、有趣或让人认出自己的生活？因果清楚，结尾兑现。",
    tip: "先写具体生活小乌龙，不堆事件，不承诺爆款。",
    prompt:
      "你是萌猫短剧导演。主角是用户选定的A版金渐层猫，米色睡衣，成年大学生，迷糊嘴硬但认真。面向喜欢轻松内容的年轻女性，设计一个低冲突、可恢复的生活乌龙。输出目标、阻力、反转与结果；再列逐镜时长、静帧、一个主动作、景别、字幕和音效。先审故事，再生图。",
  },
  {
    name: "生成生图词",
    model: "豆包 / 当前脚本模型 · 提示词整理",
    page: "script",
    gate: "人工核对身份与镜头",
    output: "每镜独立的生图词和图生视频词，分别保存。",
    check: "固定身份块保持一致；道具、机位、光线和前后状态不矛盾。",
    tip: "生图写静止起始状态；视频词写一个主动作。",
    prompt:
      "根据已确认分镜，逐镜输出两段提示词：①生图词=固定角色身份+当前静止状态+机位光线+道具；②图生视频词=以首帧开始+一个主动作+轻微环境运动+镜头行为+身份约束。每张独立9:16，留字幕空间；手机文字和闹钟数字后期添加。",
  },
  {
    name: "即梦生图",
    model: "即梦 · 账户当前可用图像模型",
    page: "assets",
    gate: "G3 逐张人工审图",
    output: "独立分镜图、模型版本、扣分与失败原因。",
    check: "脸型额纹、猫爪数量、道具形状、镜面和字幕空间四项逐张看。",
    tip: "先审图再生视频；坏一镜只修一镜，保留好图。",
    prompt:
      "使用同一身份母图，只改变当前场景和构图。保留脸型、毛色、额纹、眼色、猫爪、体型与服装。单幅竖图，主体清楚，留字幕空间。不要拼图、文字、额外角色、人手或多余肢体。",
  },
  {
    name: "图生视频",
    model: "即梦 · 账户当前可用 Seedance",
    page: "models",
    gate: "G4 完整播放每段",
    output: "已审核首帧 + 动态提示词提交包；官网生成后回传、登记任务与积分。",
    check: "完整播放中间段，看变脸、多爪、穿模、物件消失、动作是否真正发生。",
    tip: "先试简单镜与难镜。任务结果未知时先查状态，不重复扣分。",
    prompt:
      "以已审核首帧为起点，保持同一角色与现有道具，只执行一个清楚的主动作。固定机位，动作轻微自然，背景稳定，完整猫爪，不增加肢体、说话口型或文字。生成档位以账户当前模型为准。",
  },
  {
    name: "剪映编辑",
    model: "剪映专业版 · 时间线 / 字幕 / 音效 / 音乐",
    page: "edit",
    gate: "G5 完整观看与听审",
    output: "选用片段、裁点、SRT 和剪映素材交接包。",
    check:
      "字幕读得完且不挡脸；音效贴动作、音乐不盖声音、反转有停顿；核对素材权益。",
    tip: "先剪画面节奏，再配字幕与声音。交接包可导入，不能冒称原生剪映工程。",
    prompt:
      "按镜号导入已选用片段，删等待段，反转前留短停顿。字幕短句且避开脸与平台遮挡；声音贴动作点。排除非商用测试配音。导出前用手机尺寸完整观看、试听。",
  },
  {
    name: "导出复盘",
    model: "剪映导出 + 文件检测 + 平台实际数据",
    page: "delivery",
    gate: "G6 核准当前成片版本",
    output: "竖屏成片、字幕、版本审核、真实成本与24h / 72h / 7d数据。",
    check: "分开记录源分辨率与导出分辨率；当前版本完整视听，商业权益已核。",
    tip: "先记录观察，再提出假设，下一条只改一项。没有账单的费用填待核。",
    prompt:
      "记录本片实际积分、现金、会员分摊、人工分钟、生成与交付耗时、尝试次数、返工原因；未知项留空。按平台和统计窗口记录观看与收入数据，分开写观察、假设、下一条单变量实验。",
  },
];
const currentStep = computed(() => steps[step.value - 1]);
const sh = computed(
  () => shotList.value.find((x) => x.id === shotId.value) || shotList.value[0],
);
const models = computed(() =>
  list("model_profile").filter((x) => x.data.kind === "video"),
);
const approved = computed(
  () =>
    shotList.value.filter((x) => x.data.keyframe_review?.reviewed_at).length,
);
const unpriced = computed(
  () => own("cost_entry").filter((x) => x.data.unpriced).length,
);
const caseShot = computed(() => sample.value?.shots[exampleShot.value]);
const dirty = computed(
  () =>
    sh.value &&
    (draft.value.image_prompt !== (sh.value.data.image_prompt || "") ||
      draft.value.prompt !== (sh.value.data.prompt || "") ||
      draft.value.model_profile_id !== (sh.value.data.model_profile_id || "") ||
      Number(draft.value.generation_duration_s) !==
        Number(sh.value.data.generation_duration_s || sh.value.duration_s)),
);
function media(key) {
  return sample.value?.media[key];
}
function resetDraft() {
  const d = sh.value?.data || {};
  draft.value = {
    image_prompt: d.image_prompt || "",
    prompt: d.prompt || "",
    model_profile_id: d.model_profile_id || "",
    generation_duration_s: d.generation_duration_s || sh.value?.duration_s || 5,
  };
  checks.value = {};
  packagePreview.value = null;
}
watch(() => sh.value?.id, resetDraft);
watch(projectId, () => {
  shotId.value = "";
  resetDraft();
});
onMounted(async () => {
  try {
    sample.value = await api("/production/example");
    resetDraft();
  } catch (e) {
    error.value = e.message;
  }
});
async function copy(text) {
  try {
    await navigator.clipboard.writeText(text || "");
    notify("提示词已复制");
  } catch {
    notify("浏览器未允许复制，请选中文字复制", "warning");
  }
}
async function importCase() {
  const p = await act(
    () =>
      api("/production/example/import", "POST", {
        nonce: nonce.value,
        name: projectName.value,
      }),
    "已建立制作草稿，请逐步审核",
  );
  if (p) {
    nonce.value = crypto.randomUUID();
    nav("production", p.id);
    view.value = "project";
    step.value = 1;
  }
}
async function savePrompts() {
  const r = await act(
    () =>
      save(
        "shot",
        {
          revision: sh.value.revision,
          data: {
            ...sh.value.data,
            ...draft.value,
            generation_duration_s: Number(draft.value.generation_duration_s),
          },
        },
        sh.value.id,
      ),
    "提示词已保存，受影响的后续审核需重新确认",
  );
  if (r) resetDraft();
}
async function attach(e) {
  const file = e.target.files[0];
  if (!file) return;
  if (dirty.value) {
    notify("请先保存本镜设置，再回传或审核分镜图", "warning");
    e.target.value = "";
    return;
  }
  const id = sh.value.id,
    revision = sh.value.revision;
  await act(async () => {
    const f = await upload(file);
    return api("/production/shots/" + id + "/frame", "POST", {
      file_id: f.id,
      revision,
    });
  }, "分镜图已回传，请人工审核");
  checks.value = {};
  packagePreview.value = null;
  e.target.value = "";
}
async function review() {
  await act(
    () =>
      api("/production/shots/" + sh.value.id + "/frame-review", "POST", {
        checks: checks.value,
        revision: sh.value.revision,
      }),
    "当前分镜图审核已记录",
  );
  checks.value = {};
}
async function preview() {
  await act(async () => {
    packagePreview.value = await api("/shots/" + sh.value.id + "/preview");
  });
}
function jump(to) {
  nav(to, projectId.value);
}
</script>

<template>
  <div class="production-workbench">
    <div class="pw-tabs">
      <button
        :class="{ primary: view === 'example' }"
        @click="view = 'example'"
      >
        <Play :size="16" />首片实录
      </button>
      <button
        :class="{ primary: view === 'project' }"
        @click="view = 'project'"
      >
        <Clapperboard :size="16" />七步制作
      </button>
      <span>即梦会员生成 · 猫片工场管理 · 剪映交付</span>
    </div>
    <p v-if="error" class="pw-warning">{{ error }}</p>
    <template v-if="view === 'example' && sample">
      <section class="pw-hero">
        <div class="pw-film">
          <video
            v-if="media('final')?.available"
            controls
            preload="metadata"
            :poster="
              media('image01')?.available ? media('image01').url : undefined
            "
            :src="media('final').url"
          ></video>
          <p v-else class="pw-warning">
            样片素材未安装。仍可阅读完整分镜与提示词；安装首片素材包后可预览和复制制作项目。
          </p>
        </div>
        <div class="pw-intro">
          <span class="pw-eyebrow">FIRST FILM / 001 · 真实制作案例</span>
          <h2>{{ sample.title }}</h2>
          <p>{{ sample.summary }}</p>
          <div class="pw-chips">
            <span>8个镜头</span><span>38秒 · 9:16</span
            ><span>校园乌龙 / 共鸣</span><span>人工验收待完成</span>
          </div>
          <p class="pw-provenance">{{ sample.provenance }}</p>
          <dl class="pw-facts">
            <dt>源视频</dt>
            <dd>{{ sample.quality.source }}</dd>
            <dt>成片导出</dt>
            <dd>{{ sample.quality.export }}</dd>
            <dt>声音</dt>
            <dd>{{ sample.quality.audio }}</dd>
            <dt>成本</dt>
            <dd>{{ sample.cost.note }}</dd>
          </dl>
          <label
            >复制为新的制作草稿<input
              v-model="projectName"
              maxlength="60"
              aria-label="新项目名称"
          /></label>
          <button
            class="accent"
            :disabled="busy || !media('identity')?.available"
            @click="importCase"
          >
            <Copy :size="16" />用此分镜新建项目<ArrowRight :size="16" />
          </button>
          <small
            >复用A版身份与8镜草稿，不复制审片通过状态；不会消耗即梦积分。</small
          >
        </div>
      </section>
      <section class="pw-panel">
        <div class="pw-section-title">
          <h2>逐镜拆解</h2>
          <span>静帧 → 真实动态 → 迁移参考词</span>
        </div>
        <div class="pw-shot-strip">
          <button
            v-for="(s, i) in sample.shots"
            :key="i"
            :class="{ chosen: exampleShot === i }"
            @click="exampleShot = i"
          >
            <img
              v-if="media(s.image_key)?.available"
              :src="media(s.image_key).url"
              loading="lazy"
              :alt="s.name"
            /><span>{{ String(i + 1).padStart(2, "0") }} {{ s.name }}</span
            ><small>{{ s.duration_s }}秒剪辑</small>
          </button>
        </div>
        <div v-if="caseShot" class="pw-breakdown">
          <div class="pw-source">
            <video
              v-if="media(caseShot.clip_key)?.available"
              :key="caseShot.clip_key"
              :src="media(caseShot.clip_key).url"
              :poster="media(caseShot.image_key)?.url"
              controls
              preload="metadata"
            ></video>
            <p>{{ caseShot.action }}</p>
            <b>{{ caseShot.caption }}</b
            ><small
              >原段 {{ caseShot.source_duration_s }} 秒 → 剪辑
              {{ caseShot.duration_s }} 秒；{{ caseShot.sound }}</small
            >
          </div>
          <div class="pw-prompts">
            <div>
              <h3>生图参考词 <small>由现有画面重建</small></h3>
              <textarea
                readonly
                rows="5"
                :value="caseShot.image_prompt"
                aria-label="案例生图参考词"
              ></textarea
              ><button @click="copy(caseShot.image_prompt)">
                <Copy :size="14" />复制生图词
              </button>
            </div>
            <div>
              <h3>即梦图生视频参考词 <small>待账户实测</small></h3>
              <textarea
                readonly
                rows="4"
                :value="caseShot.jimeng_video_prompt"
                aria-label="即梦动态图参考词"
              ></textarea
              ><button @click="copy(caseShot.jimeng_video_prompt)">
                <Copy :size="14" />复制动态词
              </button>
            </div>
            <details>
              <summary>查看真实 Wan 提交词与任务回执</summary>
              <p class="pw-mono">{{ caseShot.actual_video_prompt }}</p>
              <small
                >任务 {{ caseShot.receipt.prompt_id }} · seed
                {{ caseShot.receipt.seed }} · {{ caseShot.receipt.frames }}帧 /
                {{ caseShot.receipt.fps }}fps</small
              >
            </details>
          </div>
        </div>
      </section>
      <section class="pw-panel">
        <h2>把这次经验带到下一条</h2>
        <ul>
          <li v-for="item in sample.lessons" :key="item">{{ item }}</li>
        </ul>
        <p class="pw-muted">
          样片尚未发布，没有平台效果或商业收入记录；它用于验证制作流程。
        </p>
      </section>
    </template>

    <template v-if="view === 'project'">
      <section class="pw-project-bar pw-panel">
        <div>
          <h2>{{ project?.name || "选择一个制作项目" }}</h2>
          <p v-if="project">
            {{ shotList.length }}镜 · 已记录审图 {{ approved }} 镜 · 待核价
            {{ unpriced }} 笔
          </p>
          <p v-else>可从首片复制草稿，或选择已有项目。</p>
        </div>
        <select
          :value="projectId"
          aria-label="制作项目"
          @change="nav('production', $event.target.value)"
        >
          <option value="">选择项目</option>
          <option v-for="p in list('project')" :value="p.id" :key="p.id">
            {{ p.name }}
          </option>
        </select>
      </section>
      <div class="pw-stepper">
        <button
          v-for="(s, i) in steps"
          :key="s.name"
          :class="{ chosen: step === i + 1 }"
          @click="step = i + 1"
        >
          <b>{{ String(i + 1).padStart(2, "0") }}</b
          ><span>{{ s.name }}</span>
        </button>
      </div>
      <section class="pw-panel pw-step-detail">
        <div class="pw-section-title">
          <div>
            <span class="pw-eyebrow">STEP {{ step }} / 07</span>
            <h2>{{ currentStep.name }}</h2>
          </div>
          <button v-if="project" @click="jump(currentStep.page)">
            进入{{ currentStep.name }}操作<ArrowRight :size="15" />
          </button>
        </div>
        <div class="pw-guide-grid">
          <div>
            <h3>使用工具</h3>
            <p>{{ currentStep.model }}</p>
            <h3>本步交付</h3>
            <p>{{ currentStep.output }}</p>
          </div>
          <div class="pw-human">
            <h3><CheckCheck :size="17" />{{ currentStep.gate }}</h3>
            <p>{{ currentStep.check }}</p>
            <small>{{ currentStep.tip }}</small>
          </div>
        </div>
        <details>
          <summary>本步通用参考提示词</summary>
          <textarea
            readonly
            rows="4"
            :value="currentStep.prompt"
            aria-label="步骤参考提示词"
          ></textarea
          ><button @click="copy(currentStep.prompt)">
            <Copy :size="14" />复制参考词
          </button>
        </details>
      </section>
      <section v-if="project && shotList.length" class="pw-panel">
        <div class="pw-section-title">
          <h2>逐镜制作台</h2>
          <select v-model="shotId" aria-label="当前分镜">
            <option value="">选择分镜（默认第一镜）</option>
            <option v-for="s in shotList" :key="s.id" :value="s.id">
              {{ s.seq + 1 }}. {{ s.name }}
            </option>
          </select>
        </div>
        <div v-if="sh" class="pw-editor">
          <div class="pw-frame">
            <img
              v-if="sh.data.keyframe_file_id"
              :src="fileUrl(sh.data.keyframe_file_id)"
              :alt="sh.name"
            />
            <div v-else class="pw-no-frame">在即梦生成后回传独立分镜图</div>
            <label class="pw-upload"
              ><Upload :size="16" />回传 / 替换分镜图<input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                :disabled="busy"
                @change="attach"
            /></label>
            <p>{{ sh.name }} · 剪辑目标 {{ sh.duration_s }}秒</p>
            <p>{{ sh.data.action }}</p>
            <small>{{
              sh.data.keyframe_review?.reviewed_at
                ? "当前图已有人工审核记录；改图、改生图词、换角色后需重审。"
                : "当前分镜图待人工审核"
            }}</small>
          </div>
          <div class="pw-prompts">
            <label
              >生图词 · 固定身份 + 静帧状态<textarea
                v-model="draft.image_prompt"
                rows="5"
                aria-label="项目生图词"
              ></textarea></label
            ><label
              >图生视频词 · 单一主动作<textarea
                v-model="draft.prompt"
                rows="5"
                aria-label="项目动态词"
              ></textarea>
            </label>
            <div class="pw-inline-fields">
              <label
                >视频模型档案<select v-model="draft.model_profile_id">
                  <option value="">使用项目默认</option>
                  <option v-for="m in models" :value="m.id" :key="m.id">
                    {{ m.name }} {{ m.data.version }}
                  </option>
                </select></label
              ><label
                >生成档位（秒）<input
                  v-model="draft.generation_duration_s"
                  type="number"
                  min="0.1"
                  max="600"
                  step="0.1"
              /></label>
            </div>
            <div class="pw-actions">
              <button class="primary" :disabled="busy" @click="savePrompts">
                保存本镜设置</button
              ><button @click="copy(draft.image_prompt)">复制生图词</button
              ><button @click="copy(draft.prompt)">复制动态词</button>
            </div>
            <small
              >生图词改动会使旧图审核失效。未保存时不能审图，请先保存本镜设置。生成时长按官网档位填写，和剪辑目标分别记录。</small
            >
          </div>
        </div>
        <div v-if="sh" class="pw-review-box">
          <h3>看过当前图后，逐项确认</h3>
          <div class="pw-checks">
            <label
              v-for="(text, key) in {
                identity: '脸 / 额纹 / 眼色 / 服装一致',
                paws: '完整猫爪，数量与身体合理',
                props: '道具形状正确，无镜面多角色',
                composition: '构图清楚，留有字幕空间',
              }"
              :key="key"
              ><input v-model="checks[key]" type="checkbox" />{{ text }}</label
            >
          </div>
          <div class="pw-actions">
            <button
              class="primary"
              :disabled="
                busy ||
                dirty ||
                !sh.data.keyframe_file_id ||
                !['identity', 'paws', 'props', 'composition'].every(
                  (k) => checks[k],
                )
              "
              @click="review"
            >
              <CheckCheck :size="15" />记录本镜人工审图</button
            ><button :disabled="busy || dirty" @click="preview">
              检查图生视频提交条件
            </button>
          </div>
        </div>
        <div v-if="packagePreview" class="pw-package">
          <h3>本镜提交检查</h3>
          <p>
            生成 {{ packagePreview.params.duration_s }}秒 / 剪辑
            {{ packagePreview.edit_duration_s }}秒 · 预计
            {{ packagePreview.estimate_credits ?? "待核" }}积分 · 人民币
            {{ yuan(packagePreview.estimate_cny) }}
          </p>
          <ul v-if="packagePreview.errors.length">
            <li v-for="e in packagePreview.errors" :key="e">{{ e }}</li>
          </ul>
          <p v-else>
            首帧和模型参数已满足检查。通过项目的前置关卡后，可在“提交与审片”导出冻结提交包。
          </p>
          <button @click="jump('review')">
            前往提交与审片<ArrowRight :size="15" />
          </button>
        </div>
      </section>
      <section v-if="project" class="pw-panel">
        <div class="pw-section-title">
          <h2>接下来</h2>
          <button @click="jump('brief')">
            项目关卡<ArrowRight :size="15" />
          </button>
        </div>
        <p>
          七步指引可随时阅读；正式导出依次完成简报、选题、分镜和资产关卡。生视频在即梦会员官网完成，回传后审片，再导出剪映素材包。
        </p>
        <div class="pw-actions">
          <button @click="jump('costs')">实际费用流水</button
          ><button @click="jump('delivery')">成片检查</button
          ><button @click="jump('retro')">发布后复盘</button>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.production-workbench {
  max-width: 1420px;
  margin: auto;
  display: grid;
  gap: 22px;
}
.pw-tabs,
.pw-actions,
.pw-section-title,
.pw-project-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.pw-tabs span {
  margin-left: auto;
  font-size: 12px;
  color: var(--muted);
}
.pw-hero {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 36px;
  padding: 28px;
  background: linear-gradient(125deg, #173e34, #255846);
  border-radius: 16px;
  color: #f8fbf5;
}
.pw-film {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a211b;
  border-radius: 11px;
  overflow: hidden;
}
.pw-film video {
  width: 100%;
  max-height: 535px;
}
.pw-intro {
  align-self: center;
}
.pw-eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.6px;
  opacity: 0.7;
}
.pw-intro h2 {
  font-size: 32px;
  margin: 13px 0;
}
.pw-intro p {
  line-height: 1.8;
}
.pw-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.pw-chips span {
  background: #ffffff16;
  border: 1px solid #ffffff24;
  border-radius: 20px;
  padding: 6px 11px;
  font-size: 12px;
}
.pw-provenance {
  color: #c1d8cc;
  font-size: 12px;
}
.pw-facts {
  display: grid;
  grid-template-columns: 70px 1fr;
  gap: 9px;
  font-size: 12px;
  line-height: 1.6;
}
.pw-facts dt {
  opacity: 0.65;
}
.pw-facts dd {
  margin: 0;
}
.pw-intro label {
  display: grid;
  gap: 7px;
  margin: 14px 0 10px;
  max-width: 450px;
  font-size: 12px;
}
.pw-intro small {
  display: block;
  color: #c1d8cc;
  font-size: 11px;
  line-height: 1.7;
  margin-top: 10px;
}
.pw-panel {
  background: white;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 24px;
}
.pw-panel h2 {
  font-size: 19px;
  margin: 0 0 14px;
}
.pw-section-title {
  justify-content: space-between;
  margin-bottom: 16px;
}
.pw-section-title h2 {
  margin: 0;
}
.pw-section-title span,
.pw-muted {
  font-size: 12px;
  color: var(--muted);
}
.pw-shot-strip {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 26px;
}
.pw-shot-strip button {
  display: flex;
  flex-direction: column;
  padding: 5px;
  white-space: normal;
  align-items: stretch;
  overflow: hidden;
  border-width: 2px;
}
.pw-shot-strip img {
  width: 100%;
  height: 124px;
  object-fit: cover;
  border-radius: 5px;
}
.pw-shot-strip span {
  font-size: 11px;
  margin: 5px 0;
}
.pw-shot-strip small {
  font-size: 10px;
  color: var(--muted);
  padding-bottom: 3px;
}
.chosen {
  border-color: #387d5c !important;
  background: #edf6ec !important;
}
.pw-breakdown,
.pw-editor {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 26px;
}
.pw-source video,
.pw-frame img {
  width: 100%;
  max-height: 465px;
  object-fit: contain;
  background: #eaf0e9;
  border-radius: 9px;
}
.pw-source p,
.pw-frame p {
  font-size: 13px;
  line-height: 1.7;
}
.pw-source small,
.pw-frame small,
.pw-prompts > small {
  display: block;
  font-size: 11px;
  line-height: 1.7;
  color: var(--muted);
  margin-top: 10px;
}
.pw-prompts {
  display: grid;
  gap: 15px;
  align-content: start;
}
.pw-prompts h3 {
  margin: 0 0 9px;
  font-size: 13px;
}
.pw-prompts h3 small {
  font-weight: 400;
  color: var(--muted);
  margin-left: 8px;
}
.pw-prompts textarea,
.pw-step-detail textarea {
  width: 100%;
  resize: vertical;
  line-height: 1.8;
  font-size: 12px;
  margin-bottom: 8px;
}
.pw-prompts label {
  display: grid;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
}
.pw-panel li {
  line-height: 1.8;
  margin: 6px 0;
}
.pw-panel details {
  padding: 12px 0;
  border-top: 1px solid var(--line);
}
.pw-panel summary {
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 10px;
}
.pw-mono {
  font-family: monospace;
  font-size: 12px;
  line-height: 1.7;
}
.pw-stepper {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 9px;
}
.pw-stepper button {
  display: grid;
  gap: 8px;
  padding: 16px 6px;
  border-radius: 10px;
}
.pw-stepper b {
  font-size: 20px;
  color: #94ad9a;
}
.pw-stepper span {
  font-size: 12px;
}
.pw-guide-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 25px;
  margin: 18px 0;
}
.pw-guide-grid h3 {
  font-size: 13px;
  display: flex;
  gap: 8px;
  align-items: center;
}
.pw-guide-grid p {
  font-size: 13px;
  line-height: 1.8;
}
.pw-human {
  background: #f1f6ee;
  border-radius: 9px;
  padding: 8px 18px;
}
.pw-human small {
  line-height: 1.7;
  color: var(--muted);
}
.pw-project-bar {
  justify-content: space-between;
}
.pw-project-bar p {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 0;
}
.pw-inline-fields {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 15px;
}
.pw-upload {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  position: relative;
  background: #edf4e9;
  border: 1px dashed #9db69e;
  padding: 12px;
  border-radius: 7px;
  margin-top: 12px;
  cursor: pointer;
  font-size: 12px;
}
.pw-upload input {
  position: absolute;
  inset: 0;
  opacity: 0;
  width: 100%;
  cursor: pointer;
}
.pw-review-box {
  border-top: 1px solid var(--line);
  margin-top: 25px;
  padding-top: 15px;
}
.pw-review-box h3,
.pw-package h3 {
  font-size: 14px;
}
.pw-checks {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 18px 0;
}
.pw-checks label {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
}
.pw-checks input {
  width: auto;
}
.pw-package {
  background: #f5f6ef;
  padding: 15px 20px;
  border-radius: 8px;
  margin-top: 20px;
  font-size: 12px;
}
.pw-no-frame {
  height: 300px;
  display: grid;
  place-items: center;
  background: #edf2eb;
  border-radius: 8px;
  color: var(--muted);
  padding: 20px;
}
.pw-warning {
  padding: 16px;
  background: #fff0db;
  color: #775724;
  font-size: 13px;
  line-height: 1.8;
}
.pw-actions {
  flex-wrap: wrap;
}
@media (max-width: 1150px) {
  .pw-hero {
    grid-template-columns: 240px 1fr;
    gap: 24px;
  }
  .pw-shot-strip {
    grid-template-columns: repeat(4, 1fr);
  }
  .pw-shot-strip img {
    height: 150px;
  }
  .pw-stepper {
    grid-template-columns: repeat(4, 1fr);
  }
}
@media (max-width: 760px) {
  .pw-hero,
  .pw-breakdown,
  .pw-editor,
  .pw-guide-grid {
    grid-template-columns: 1fr;
  }
  .pw-film video {
    max-height: 460px;
  }
  .pw-intro h2 {
    font-size: 25px;
  }
  .pw-checks {
    grid-template-columns: 1fr;
  }
  .pw-tabs span {
    display: none;
  }
  .pw-stepper {
    grid-template-columns: repeat(3, 1fr);
  }
  .pw-project-bar {
    flex-wrap: wrap;
  }
  .pw-shot-strip img {
    height: 110px;
  }
}
</style>
