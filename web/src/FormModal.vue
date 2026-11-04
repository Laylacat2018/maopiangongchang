<script setup>
import { ref, watch } from "vue";
const props = defineProps({ model: Object });
const emit = defineEmits(["close", "submit"]);
const values = ref({});
const error = ref("");
const submitting = ref(false);
watch(
  () => props.model,
  (m) => {
    if (m) {
      values.value = JSON.parse(JSON.stringify(m.values || {}));
      error.value = "";
    }
  },
  { immediate: true },
);
async function submit() {
  if (submitting.value) return;
  submitting.value = true;
  error.value = "";
  try {
    for (const f of props.model.fields) {
      if (
        f.required &&
        (values.value[f.key] === undefined ||
          values.value[f.key] === null ||
          String(values.value[f.key]).trim() === "")
      )
        throw new Error("请填写" + f.label);
      if (f.type === "json" && typeof values.value[f.key] === "string")
        values.value[f.key] = JSON.parse(values.value[f.key]);
    }
    await props.model.submit(values.value);
    emit("close");
  } catch (e) {
    error.value = e.message;
  } finally {
    submitting.value = false;
  }
}
function files(e, k) {
  values.value[k] = e.target.files[0];
}
</script>
<template>
  <Teleport to="body"
    ><div v-if="model" class="modal-shade" @click.self="$emit('close')">
      <section
        class="modal"
        role="dialog"
        aria-modal="true"
        :aria-label="model.title"
      >
        <header>
          <h2>{{ model.title }}</h2>
          <button class="icon-btn" aria-label="关闭" @click="$emit('close')">
            ×
          </button>
        </header>
        <p v-if="model.description" class="muted">{{ model.description }}</p>
        <form @submit.prevent="submit">
          <div class="modal-fields">
            <div
              v-for="f in model.fields"
              :key="f.key"
              class="field"
              :class="{ full: f.wide }"
            >
              <span>{{ f.label }} <em v-if="f.required">*</em></span
              ><textarea
                :aria-label="f.label"
                v-if="['textarea', 'json'].includes(f.type)"
                v-model="values[f.key]"
                :rows="f.rows || 3"
                :required="f.required"
                :placeholder="f.placeholder"
              /><select
                :aria-label="f.label"
                v-else-if="f.type === 'select'"
                v-model="values[f.key]"
                :required="f.required"
              >
                <option value="">请选择</option>
                <option
                  v-for="o in f.options"
                  :key="o.value ?? o"
                  :value="o.value ?? o"
                >
                  {{ o.label ?? o }}
                </option>
              </select>
              <div v-else-if="f.type === 'checks'" class="check-options">
                <label v-for="o in f.options" :key="o.value"
                  ><input type="checkbox" v-model="values[o.value]" />{{
                    o.label
                  }}</label
                >
              </div>
              <input
                :aria-label="f.label"
                v-else-if="f.type === 'file'"
                type="file"
                :accept="f.accept"
                @change="files($event, f.key)"
                :required="f.required"
              /><input
                :aria-label="f.label"
                v-else-if="f.type === 'checkbox'"
                type="checkbox"
                v-model="values[f.key]"
              /><input
                :aria-label="f.label"
                v-else
                v-model="values[f.key]"
                :type="f.type || 'text'"
                :required="f.required"
                :min="f.min"
                :max="f.max"
                :step="f.step || 'any'"
                :placeholder="f.placeholder"
                :maxlength="f.maxlength"
              /><small v-if="f.help">{{ f.help }}</small>
            </div>
          </div>
          <p v-if="error" class="error-text" role="alert">{{ error }}</p>
          <footer>
            <button type="button" @click="$emit('close')">取消</button
            ><button type="submit" class="primary" :disabled="submitting">
              {{ model.submitLabel || "保存" }}
            </button>
          </footer>
        </form>
      </section>
    </div></Teleport
  >
</template>
