<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { getHighestPhase, mergeRuntimeEvents } from "./eventState";
import { buildConfigPayload } from "./workbenchFlow";

const views = [
  ["workbench", "创作"],
  ["jobs", "任务"],
  ["materials", "素材"],
  ["artifacts", "产物"],
];
const STORAGE = "crayotter.vue.current-view";
const currentView = ref(localStorage.getItem(STORAGE) || "workbench");
const jobs = ref([]);
const uploads = ref([]);
const selectedJobId = ref(null);
const selectedJob = ref(null);
const selectedEvents = ref([]);
const selectedMessages = ref([]);
const selectedPlan = ref(null);
const loading = ref(false);
const uploading = ref(false);
const settingsOpen = ref(false);
const toasts = ref([]);
const eventSource = ref(null);
const taskText = ref("");
const taskMode = ref("agent");
const taskDuration = ref(15);
const createOptions = reactive({ enablePhase2Research: true, enablePlanReview: true, directPhase3Execution: false, preferLocalMaterials: true });
const planFeedback = ref("");
const configMessage = ref("");

const configForm = reactive({
  apiKey: "", baseUrl: "", model: "", videoApiKey: "", videoBaseUrl: "", videoModel: "",
  ttsApiKey: "", ttsBaseUrl: "", ttsModel: "", enablePhase2Research: true,
  enablePlanReview: true, directPhase3Execution: false, preferLocalMaterials: false,
  stallTimeout: 150, youtubeMode: "auto", enabledMaterialPlatforms: "bilibili,douyin,xiaohongshu,youtube",
  defaultDeadlineSeconds: 600, processingMode: "auto", outputProfile: "auto", browserAuthBrowser: "", browserAuthProfile: "",
});

const request = async (url, options = {}) => {
  const headers = options.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  const response = await fetch(url, { ...options, headers: { ...headers, ...(options.headers || {}) } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || body.error || `${response.status} ${response.statusText}`);
  }
  const type = response.headers.get("content-type") || "";
  return type.includes("application/json") ? response.json() : response.text();
};

const fileUrl = (path, download = false) => `/files?path=${encodeURIComponent(path)}${download ? "&download=1" : ""}`;
const formatDate = (value) => value ? new Date(value).toLocaleString() : "—";
const formatBytes = (value) => {
  const bytes = Number(value || 0);
  if (!bytes) return "—";
  return bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};
const titleFor = (job) => String(job?.title || job?.task || "未命名任务").slice(0, 56);
const statusLabel = (status) => ({ queued: "等待中", running: "执行中", completed: "已完成", failed: "失败", cancelled: "已取消", interrupted: "已中断" })[status] || status || "未知";
const notify = (message, type = "info") => {
  const id = `${Date.now()}-${Math.random()}`;
  toasts.value.push({ id, message, type });
  window.setTimeout(() => dismissToast(id), 4200);
};
const dismissToast = (id) => { toasts.value = toasts.value.filter((item) => item.id !== id); };
const setView = (view) => { currentView.value = view; localStorage.setItem(STORAGE, view); };

const meaningfulEvents = computed(() => selectedEvents.value.filter((event) => !["scheduler_event", "checkpoint_saved"].includes(event.type)));
const currentPhase = computed(() => getHighestPhase(selectedEvents.value));
const artifacts = computed(() => selectedJob.value?.artifacts || []);
const activePlan = computed(() => selectedPlan.value?.plan || null);
const planNeedsReview = computed(() => ["DRAFT", "VALIDATED", "WAITING_FOR_USER_REVIEW", "REVISING", "REJECTED"].includes(String(activePlan.value?.status || "").toUpperCase()));

function closeStream() {
  eventSource.value?.close();
  eventSource.value = null;
}

async function loadConfig() {
  const config = await request("/config");
  const profile = config.profiles?.[config.active_profile || "default"] || {};
  Object.assign(configForm, {
    apiKey: profile.api_key || "", baseUrl: profile.base_url || "", model: profile.model_name || "",
    videoApiKey: profile.video_api_key || "", videoBaseUrl: profile.video_base_url || "", videoModel: profile.video_model_name || "",
    ttsApiKey: profile.tts_api_key || "", ttsBaseUrl: profile.tts_base_url || "", ttsModel: profile.tts_model_name || "",
    enablePhase2Research: Boolean(config.enable_phase2_research), enablePlanReview: config.enable_plan_review !== false,
    directPhase3Execution: Boolean(config.direct_phase3_execution), preferLocalMaterials: Boolean(config.prefer_local_materials),
    stallTimeout: config.agent_stall_timeout_seconds || 150, youtubeMode: config.youtube_mode || "auto",
    enabledMaterialPlatforms: (config.enabled_material_platforms || []).join(","), defaultDeadlineSeconds: config.default_deadline_seconds || 600,
    processingMode: config.processing_mode || "auto", outputProfile: config.output_profile || "auto",
    browserAuthBrowser: config.browser_auth_browser || "", browserAuthProfile: config.browser_auth_profile || "",
  });
  Object.assign(createOptions, {
    enablePhase2Research: configForm.enablePhase2Research, enablePlanReview: configForm.enablePlanReview,
    directPhase3Execution: configForm.directPhase3Execution, preferLocalMaterials: configForm.preferLocalMaterials,
  });
}

async function saveConfig() {
  try {
    await request("/config", { method: "PUT", body: JSON.stringify(buildConfigPayload(configForm)) });
    configMessage.value = "配置已保存";
    notify("配置已保存", "success");
  } catch (error) { configMessage.value = error.message; notify(error.message, "error"); }
}

async function loadUploads() { uploads.value = (await request("/uploads")).items || []; }
async function refreshJobs(selectNewest = false) {
  jobs.value = (await request("/jobs")).items || [];
  if (selectNewest && !selectedJobId.value && jobs.value[0]) await selectJob(jobs.value[0].job_id);
}

async function loadPlan(job) {
  try { selectedPlan.value = await request(`/jobs/${job.job_id}/plans/current`); }
  catch (_) { selectedPlan.value = null; }
}

async function selectJob(jobId) {
  closeStream();
  selectedJobId.value = jobId;
  try {
    const [job, events, messages] = await Promise.all([
      request(`/jobs/${jobId}`), request(`/jobs/${jobId}/events`), request(`/jobs/${jobId}/messages`),
    ]);
    selectedJob.value = job;
    selectedEvents.value = events.items || [];
    selectedMessages.value = messages.items || [];
    await loadPlan(job);
    startStream(job);
  } catch (error) { notify(`读取任务失败：${error.message}`, "error"); }
}

function startStream(job) {
  const after = Math.max(0, ...selectedEvents.value.map((event) => Number(event.sequence || 0)));
  const source = new EventSource(`/jobs/${job.job_id}/events/stream?after=${after}`);
  eventSource.value = source;
  source.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data);
      selectedEvents.value = mergeRuntimeEvents(selectedEvents.value, [event]);
      selectedJob.value = { ...selectedJob.value, processing_elapsed_seconds: event.payload?.processing_elapsed_seconds ?? selectedJob.value.processing_elapsed_seconds };
      if (["job_completed", "job_failed", "job_cancelled"].includes(event.type)) {
        refreshJobs();
        request(`/jobs/${job.job_id}`).then((detail) => { selectedJob.value = detail; loadPlan(detail); });
      }
    } catch (_) { /* ignore malformed event */ }
  };
  source.onerror = () => source.close();
}

async function createJob() {
  if (!taskText.value.trim()) return notify("请输入视频制作需求", "error");
  loading.value = true;
  try {
    const job = await request("/jobs", {
      method: "POST",
      body: JSON.stringify({
        task: taskText.value.trim(), mode: taskMode.value, target_duration_seconds: Number(taskDuration.value) || undefined,
        enable_phase2_research: createOptions.enablePhase2Research, enable_plan_review: createOptions.enablePlanReview,
        direct_phase3_execution: createOptions.directPhase3Execution, prefer_local_materials: createOptions.preferLocalMaterials,
      }),
    });
    taskText.value = "";
    await refreshJobs();
    await selectJob(job.job_id);
    setView("workbench");
    notify("任务已创建", "success");
  } catch (error) { notify(`创建任务失败：${error.message}`, "error"); }
  finally { loading.value = false; }
}

async function cancelJob() { if (!selectedJob.value) return; await action(`/jobs/${selectedJob.value.job_id}/cancel`, "任务已取消"); }
async function resumeJob(jobId = selectedJob.value?.job_id) { if (jobId) await action(`/jobs/${jobId}/resume`, "任务已恢复"); }
async function action(url, message) {
  try { await request(url, { method: "POST", body: "{}" }); await refreshJobs(); if (selectedJobId.value) await selectJob(selectedJobId.value); notify(message, "success"); }
  catch (error) { notify(error.message, "error"); }
}
async function deleteJob(jobId) {
  if (!window.confirm("确认删除该任务及其记录？")) return;
  try { await request(`/jobs/${jobId}`, { method: "DELETE" }); if (selectedJobId.value === jobId) { closeStream(); selectedJobId.value = null; selectedJob.value = null; selectedEvents.value = []; } await refreshJobs(); notify("任务已删除", "success"); }
  catch (error) { notify(error.message, "error"); }
}
async function uploadFiles(event) {
  const files = [...(event.target.files || [])];
  if (!files.length) return;
  uploading.value = true;
  try { const form = new FormData(); files.forEach((file) => form.append("files", file)); await request("/uploads", { method: "POST", body: form }); await loadUploads(); notify("素材上传成功", "success"); }
  catch (error) { notify(`上传失败：${error.message}`, "error"); }
  finally { uploading.value = false; event.target.value = ""; }
}
async function deleteUpload(path) {
  if (!window.confirm("确认删除该素材？")) return;
  try { await request(`/uploads?path=${encodeURIComponent(path)}`, { method: "DELETE" }); await loadUploads(); notify("素材已删除", "success"); }
  catch (error) { notify(error.message, "error"); }
}
async function sendGuidance() {
  if (!selectedJob.value || !taskText.value.trim()) return;
  try { await request(`/jobs/${selectedJob.value.job_id}/messages`, { method: "POST", body: JSON.stringify({ content: taskText.value.trim() }) }); taskText.value = ""; selectedMessages.value = (await request(`/jobs/${selectedJob.value.job_id}/messages`)).items || []; notify("指导已发送", "success"); }
  catch (error) { notify(error.message, "error"); }
}
async function submitPlan(action) {
  if (!selectedJob.value || !activePlan.value) return;
  const version = activePlan.value.version;
  try {
    const body = action === "feedback" ? JSON.stringify({ feedback: planFeedback.value }) : "{}";
    await request(`/jobs/${selectedJob.value.job_id}/plans/${version}/${action}`, { method: "POST", body });
    planFeedback.value = ""; await loadPlan(selectedJob.value); notify("计划操作已提交", "success");
  } catch (error) { notify(error.message, "error"); }
}

watch(currentView, (view) => localStorage.setItem(STORAGE, view));
onMounted(async () => {
  try { await Promise.all([loadConfig(), loadUploads(), refreshJobs(true), request("/health")]); }
  catch (error) { notify(`后端连接失败：${error.message}`, "error"); }
});
onBeforeUnmount(closeStream);
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <header class="sticky top-0 z-20 flex items-center justify-between border-b bg-white px-4 py-3 shadow-sm">
      <button class="text-lg font-bold" type="button" @click="setView('workbench')">Crayotter <span class="text-sm font-normal text-slate-400">Vue 工作台</span></button>
      <div class="flex items-center gap-2"><label class="secondary-button cursor-pointer"><input class="hidden" type="file" multiple accept="video/*" @change="uploadFiles" />{{ uploading ? '上传中…' : '上传素材' }}</label><button class="secondary-button" type="button" @click="settingsOpen = true">设置</button></div>
    </header>
    <div class="grid min-h-[calc(100vh-57px)] md:grid-cols-[220px_minmax(0,1fr)]">
      <aside class="border-r bg-white p-3"><nav class="grid gap-1"><button v-for="[id, label] in views" :key="id" type="button" class="rounded-lg px-3 py-2 text-left" :class="currentView === id ? 'bg-blue-600 text-white' : 'hover:bg-slate-100'" @click="setView(id)">{{ label }}</button></nav><hr class="my-4" /><p class="px-3 text-xs text-slate-500">最近任务</p><button v-for="job in jobs.slice(0, 6)" :key="job.job_id" class="mt-1 w-full rounded p-2 text-left text-sm hover:bg-slate-100" :class="selectedJobId === job.job_id ? 'bg-blue-50' : ''" type="button" @click="selectJob(job.job_id)"><span class="block truncate">{{ titleFor(job) }}</span><span class="text-xs text-slate-500">{{ statusLabel(job.status) }}</span></button></aside>
      <main class="min-w-0 p-4 md:p-6">
        <section v-if="currentView === 'workbench'" class="mx-auto max-w-6xl space-y-5">
          <div class="rounded-2xl bg-gradient-to-br from-blue-700 to-indigo-700 p-6 text-white"><h1 class="text-2xl font-bold">创建 AI 视频任务</h1><p class="mt-2 text-blue-100">描述你希望生成的视频，系统会自动完成素材、剪辑、旁白和字幕。</p><textarea v-model="taskText" class="mt-5 min-h-28 w-full rounded-xl border-0 p-3 text-slate-900" placeholder="例如：制作一个 15 秒高张力的游戏战斗剪辑，包含旁白和字幕。" /><div class="mt-3 flex flex-wrap items-center gap-3"><label>时长 <input v-model.number="taskDuration" class="ml-1 w-20 rounded p-1 text-slate-900" min="5" type="number" /></label><select v-model="taskMode" class="rounded p-1 text-slate-900"><option value="agent">真实 Agent</option><option value="demo">演示模式</option></select><label><input v-model="createOptions.enablePhase2Research" type="checkbox" /> Phase 2</label><label><input v-model="createOptions.enablePlanReview" type="checkbox" /> 计划审批</label><label><input v-model="createOptions.preferLocalMaterials" type="checkbox" /> 优先本地素材</label><button class="rounded bg-white px-4 py-2 font-medium text-blue-700" :disabled="loading" type="button" @click="selectedJob ? sendGuidance() : createJob()">{{ selectedJob?.status === 'running' ? '发送指导' : loading ? '创建中…' : '开始生成' }}</button></div></div>
          <div v-if="selectedJob" class="grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(280px,1fr)]"><section class="rounded-xl border bg-white p-5"><div class="flex flex-wrap items-start justify-between gap-3"><div><p class="text-sm text-slate-500">当前任务</p><h2 class="text-lg font-semibold">{{ titleFor(selectedJob) }}</h2><p class="mt-1 text-sm">状态：<b>{{ statusLabel(selectedJob.status) }}</b> · 阶段：{{ currentPhase || '准备中' }}</p></div><div class="flex gap-2"><button v-if="['running','queued'].includes(selectedJob.status)" class="danger-button" type="button" @click="cancelJob">取消</button><button v-if="selectedJob.status === 'interrupted'" class="secondary-button" type="button" @click="resumeJob()">恢复</button></div></div><div v-if="planNeedsReview" class="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-4"><h3 class="font-semibold">等待计划审批：{{ activePlan.version }}</h3><pre class="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs">{{ activePlan.content || activePlan.summary || selectedPlan }}</pre><textarea v-model="planFeedback" class="mt-3 w-full rounded border p-2" placeholder="输入修改意见后提交，或直接批准计划" /><div class="mt-2 flex gap-2"><button class="secondary-button" type="button" @click="submitPlan('feedback')">提交意见</button><button class="primary-button" type="button" @click="submitPlan('approve')">批准</button><button class="danger-button" type="button" @click="submitPlan('reject')">拒绝</button></div></div><h3 class="mt-5 font-semibold">实时事件</h3><ol class="mt-2 max-h-96 space-y-2 overflow-auto"><li v-for="event in meaningfulEvents.slice(-80)" :key="event.sequence || event.timestamp" class="rounded bg-slate-50 p-2 text-sm"><span class="font-medium">{{ event.type }}</span><span class="ml-2 text-slate-500">{{ event.payload?.summary || event.payload?.message || JSON.stringify(event.payload || {}) }}</span></li></ol></section><aside class="rounded-xl border bg-white p-5"><h3 class="font-semibold">结果与产物</h3><p class="mt-2 text-sm text-slate-600">{{ selectedJob.final_output || selectedJob.error || '任务执行后将在此显示结果。' }}</p><a v-for="path in selectedJob.output_files || []" :key="path" class="mt-3 block text-sm text-blue-600 underline" :href="fileUrl(path, true)">{{ path.split(/[\\/]/).pop() }}</a><p v-if="!selectedJob.output_files?.length" class="mt-3 text-sm text-slate-400">暂无最终文件</p></aside></div>
          <div v-else class="rounded-xl border border-dashed bg-white p-10 text-center text-slate-500">创建任务后，可在这里查看实时进度、计划审批和最终视频。</div>
        </section>

        <section v-else-if="currentView === 'jobs'" class="mx-auto max-w-6xl"><div class="mb-4 flex items-center justify-between"><h1 class="text-2xl font-bold">任务管理</h1><button class="secondary-button" type="button" @click="refreshJobs()">刷新</button></div><div class="overflow-hidden rounded-xl border bg-white"><table class="w-full text-left text-sm"><thead class="bg-slate-50 text-slate-500"><tr><th class="p-3">任务</th><th class="p-3">状态</th><th class="p-3">创建时间</th><th class="p-3">操作</th></tr></thead><tbody><tr v-for="job in jobs" :key="job.job_id" class="border-t"><td class="p-3"><button class="text-left font-medium hover:text-blue-600" type="button" @click="selectJob(job.job_id); setView('workbench')">{{ titleFor(job) }}</button></td><td class="p-3">{{ statusLabel(job.status) }}</td><td class="p-3 text-slate-500">{{ formatDate(job.created_at) }}</td><td class="p-3"><button v-if="job.status === 'interrupted'" class="mr-2 text-blue-600" type="button" @click="resumeJob(job.job_id)">恢复</button><button class="text-red-600" type="button" @click="deleteJob(job.job_id)">删除</button></td></tr></tbody></table></div></section>

        <section v-else-if="currentView === 'materials'" class="mx-auto max-w-6xl"><div class="mb-4 flex items-center justify-between"><h1 class="text-2xl font-bold">本地素材</h1><label class="primary-button cursor-pointer"><input class="hidden" type="file" multiple accept="video/*" @change="uploadFiles" />上传视频</label></div><div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><article v-for="item in uploads" :key="item.path" class="rounded-xl border bg-white p-4"><h2 class="truncate font-medium">{{ item.name }}</h2><p class="mt-1 text-sm text-slate-500">{{ formatBytes(item.size_bytes) }} · {{ formatDate(item.modified_at) }}</p><p class="mt-2 text-sm" :class="item.has_analysis ? 'text-emerald-600' : 'text-amber-600'">{{ item.has_analysis ? '已有分析结果' : '尚未分析' }}</p><div class="mt-3 flex gap-2"><button class="secondary-button" type="button" @click="taskText = `优先使用本地素材：${item.display_path}`; setView('workbench')">用于任务</button><button class="danger-button" type="button" @click="deleteUpload(item.display_path)">删除</button></div></article><p v-if="!uploads.length" class="text-slate-500">暂无上传素材。</p></div></section>

        <section v-else class="mx-auto max-w-6xl"><h1 class="mb-4 text-2xl font-bold">任务产物</h1><p v-if="!selectedJob" class="text-slate-500">请先从任务页面选择一个任务。</p><div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><article v-for="path in selectedJob.output_files || []" :key="path" class="rounded-xl border bg-white p-4"><h2 class="truncate font-medium">{{ path.split(/[\\/]/).pop() }}</h2><video class="mt-3 w-full rounded bg-black" controls :src="fileUrl(path)" /><a class="mt-3 block text-blue-600 underline" :href="fileUrl(path, true)">下载文件</a></article><p v-if="!selectedJob.output_files?.length" class="text-slate-500">该任务暂无可交付产物。</p></div></section>
      </main>
    </div>

    <div v-if="settingsOpen" class="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 p-4"><section class="max-h-[90vh] w-full max-w-3xl overflow-auto rounded-2xl bg-white p-6"><div class="flex items-center justify-between"><h2 class="text-xl font-bold">运行配置</h2><button type="button" @click="settingsOpen = false">关闭</button></div><form class="mt-5 space-y-5" @submit.prevent="saveConfig"><div class="grid gap-4 md:grid-cols-2"><label>API Key<input v-model="configForm.apiKey" type="password" /></label><label>模型<input v-model="configForm.model" placeholder="qwen-plus" /></label><label>Base URL<input v-model="configForm.baseUrl" placeholder="https://.../v1" /></label><label>视频模型<input v-model="configForm.videoModel" /></label><label>视频 API Key<input v-model="configForm.videoApiKey" type="password" /></label><label>TTS 模型<input v-model="configForm.ttsModel" /></label><label>TTS API Key<input v-model="configForm.ttsApiKey" type="password" /></label><label>任务超时（秒）<input v-model.number="configForm.defaultDeadlineSeconds" type="number" /></label><label>卡死超时（秒）<input v-model.number="configForm.stallTimeout" type="number" /></label><label>素材平台<input v-model="configForm.enabledMaterialPlatforms" /></label><label>处理模式<select v-model="configForm.processingMode"><option>auto</option><option>speed</option><option>quality</option></select></label><label>输出规格<input v-model="configForm.outputProfile" /></label></div><div class="flex flex-wrap gap-4"><label><input v-model="configForm.enablePhase2Research" type="checkbox" /> 启用 Phase 2</label><label><input v-model="configForm.enablePlanReview" type="checkbox" /> 启用计划审批</label><label><input v-model="configForm.directPhase3Execution" type="checkbox" /> 直接执行 Phase 3</label><label><input v-model="configForm.preferLocalMaterials" type="checkbox" /> 优先本地素材</label></div><p class="text-sm text-slate-500">{{ configMessage }}</p><div class="flex justify-end gap-2"><button class="secondary-button" type="button" @click="loadConfig">重新读取</button><button class="primary-button" type="submit">保存配置</button></div></form></section></div>
    <div class="fixed bottom-4 right-4 z-[60] grid gap-2"><div v-for="toast in toasts" :key="toast.id" class="rounded-lg bg-slate-900 px-4 py-3 text-sm text-white shadow-lg"><button class="float-right ml-4" type="button" @click="dismissToast(toast.id)">×</button>{{ toast.message }}</div></div>
  </div>
</template>
