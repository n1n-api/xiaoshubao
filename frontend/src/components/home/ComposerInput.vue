<template>
  <!-- 主题输入组合框 -->
  <div class="composer-container">
    <!-- 输入区域 -->
    <div class="composer-input-wrapper">
      <div class="search-icon-static">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M21 21L16.65 16.65M19 11C19 15.4183 15.4183 19 11 19C6.58172 19 3 15.4183 3 11C3 6.58172 6.58172 3 11 3C15.4183 3 19 6.58172 19 11Z" stroke="#999" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <textarea
        ref="textareaRef"
        :value="modelValue"
        @input="handleInput"
        class="composer-textarea"
        placeholder="输入你的灵感，例如：秋季显白美甲、周末探店、减脂餐..."
        @keydown.enter.prevent="handleEnter"
        :disabled="loading"
        rows="1"
      ></textarea>
    </div>

    <!-- 灵感气泡提示 -->
    <div class="inspiration-bubbles" v-if="!modelValue && uploadedImages.length === 0">
      <span class="bubble-label">试试输入：</span>
      <button class="bubble-item" @click="applyInspiration('平价口红推荐')">💄 平价口红</button>
      <button class="bubble-item" @click="applyInspiration('周末去哪玩')">🗺️ 周末去哪玩</button>
      <button class="bubble-item" @click="applyInspiration('沉浸式护肤')">🧖‍♀️ 沉浸式护肤</button>
      <button class="bubble-item" @click="applyInspiration('懒人减脂餐')">🥗 懒人减脂餐</button>
    </div>

    <!-- 已上传图片预览 -->
    <div v-if="uploadedImages.length > 0" class="uploaded-images-preview">
      <div
        v-for="(img, idx) in uploadedImages"
        :key="idx"
        class="uploaded-image-item"
      >
        <img :src="img.preview" :alt="`图片 ${idx + 1}`" />
        <button class="remove-image-btn" @click="removeImage(idx)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="upload-hint">
        已添加参考图，AI将提取图片风格与内容
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="composer-toolbar">
      <div class="toolbar-left">
        <label class="tool-btn" :class="{ 'active': uploadedImages.length > 0 }" title="上传参考图">
          <input
            type="file"
            accept="image/*"
            multiple
            @change="handleImageUpload"
            :disabled="loading"
            style="display: none;"
          />
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <circle cx="8.5" cy="8.5" r="1.5"></circle>
            <polyline points="21 15 16 10 5 21"></polyline>
          </svg>
          <span v-if="uploadedImages.length > 0" class="badge-count">{{ uploadedImages.length }}</span>
        </label>
      </div>
      <div class="toolbar-right">
        <button
          class="btn btn-primary generate-btn"
          @click="$emit('generate')"
          :disabled="!modelValue.trim() || loading"
        >
          <span v-if="loading" class="spinner-sm"></span>
          <span v-else>✨ 唤醒灵感</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'

/**
 * 主题输入组合框组件
 *
 * 功能：
 * - 主题文本输入（自动调整高度）
 * - 参考图片上传（最多5张）
 * - 灵感气泡提示
 * - 生成按钮
 */

// 定义上传的图片类型
interface UploadedImage {
  file: File
  preview: string
}

// 定义 Props
const props = defineProps<{
  modelValue: string
  loading: boolean
}>()

// 定义 Emits
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'generate'): void
  (e: 'imagesChange', images: File[]): void
}>()

// 输入框引用
const textareaRef = ref<HTMLTextAreaElement | null>(null)

// 已上传的图片
const uploadedImages = ref<UploadedImage[]>([])

/**
 * 处理输入变化
 */
function handleInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('update:modelValue', target.value)
  adjustHeight()
}

/**
 * 应用灵感提示
 */
function applyInspiration(text: string) {
  emit('update:modelValue', text)
  // 聚焦并自动调整高度
  if (textareaRef.value) {
    textareaRef.value.focus()
    // 微小延迟确保值更新后计算高度
    setTimeout(() => {
      adjustHeight()
    }, 0)
  }
}

/**
 * 处理回车键
 */
function handleEnter(e: KeyboardEvent) {
  if (e.shiftKey) return // 允许 Shift+Enter 换行
  emit('generate')
}

/**
 * 自动调整输入框高度
 */
function adjustHeight() {
  const el = textareaRef.value
  if (!el) return

  el.style.height = 'auto'
  const newHeight = Math.max(64, Math.min(el.scrollHeight, 200))
  el.style.height = newHeight + 'px'
}

/**
 * 处理图片上传
 */
function handleImageUpload(event: Event) {
  const target = event.target as HTMLInputElement
  if (!target.files) return

  const files = Array.from(target.files)
  files.forEach((file) => {
    // 限制最多 5 张图片
    if (uploadedImages.value.length >= 5) {
      return
    }
    // 创建预览 URL
    const preview = URL.createObjectURL(file)
    uploadedImages.value.push({ file, preview })
  })

  // 通知父组件
  emitImagesChange()

  // 清空 input，允许重复选择同一文件
  target.value = ''
}

/**
 * 移除图片
 */
function removeImage(index: number) {
  const img = uploadedImages.value[index]
  // 释放预览 URL
  URL.revokeObjectURL(img.preview)
  uploadedImages.value.splice(index, 1)

  // 通知父组件
  emitImagesChange()
}

/**
 * 通知父组件图片变化
 */
function emitImagesChange() {
  const files = uploadedImages.value.map(img => img.file)
  emit('imagesChange', files)
}

/**
 * 清理所有预览 URL
 */
function clearPreviews() {
  uploadedImages.value.forEach(img => URL.revokeObjectURL(img.preview))
  uploadedImages.value = []
}

// 组件卸载时清理
onUnmounted(() => {
  clearPreviews()
})

// 暴露方法给父组件
defineExpose({
  clearPreviews
})
</script>

<style scoped>
/* 组合框容器 */
.composer-container {
  background: white;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(0, 0, 0, 0.04);
  transition: all 0.3s ease;
}

.composer-container:focus-within {
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1);
  border-color: var(--primary-fade);
}

/* 输入区域 */
.composer-input-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.search-icon-static {
  flex-shrink: 0;
  padding-top: 10px;
  color: var(--text-placeholder);
}

.composer-textarea {
  flex: 1;
  border: none;
  outline: none;
  font-size: 16px;
  line-height: 1.6;
  resize: none;
  min-height: 44px;
  max-height: 200px;
  padding: 10px 0;
  font-family: inherit;
  color: var(--text-main);
  background: transparent;
}

.composer-textarea::placeholder {
  color: var(--text-placeholder);
}

.composer-textarea:disabled {
  background: transparent;
  color: var(--text-placeholder);
}

/* 灵感气泡 */
.inspiration-bubbles {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-left: 38px; /* 对齐输入框文字 */
  margin-top: 4px;
  margin-bottom: 8px;
  animation: fadeIn 0.3s ease-out;
}

.bubble-label {
  font-size: 12px;
  color: var(--text-sub);
}

.bubble-item {
  background: #F7F8FA;
  border: 1px solid transparent;
  border-radius: 100px;
  padding: 4px 12px;
  font-size: 12px;
  color: var(--text-sub);
  cursor: pointer;
  transition: all 0.2s ease;
}

.bubble-item:hover {
  background: var(--primary-light);
  color: var(--primary);
  border-color: rgba(255, 36, 66, 0.1);
}

/* 已上传图片预览 */
.uploaded-images-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
  padding: 16px;
  background: #fafafa;
  border-radius: 12px;
  align-items: center;
}

.uploaded-image-item {
  position: relative;
  width: 60px;
  height: 60px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.uploaded-image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.remove-image-btn {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  opacity: 0;
  transition: opacity 0.2s;
}

.uploaded-image-item:hover .remove-image-btn {
  opacity: 1;
}

.remove-image-btn:hover {
  background: var(--primary);
}

.upload-hint {
  flex: 1;
  font-size: 12px;
  color: var(--text-sub);
  text-align: right;
}

/* 工具栏 */
.composer-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding-top: 16px;
  border-top: 1px solid #f4f4f4;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #F7F8FA;
  border: none;
  cursor: pointer;
  color: var(--text-sub);
  transition: all 0.2s;
}

.tool-btn:hover {
  background: #eee;
  color: var(--text-main);
}

.tool-btn.active {
  background: var(--primary-light);
  color: var(--primary);
}

.badge-count {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  background: var(--primary);
  color: white;
  border-radius: 9px;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
  border: 2px solid white;
}

/* 生成按钮 */
.generate-btn {
  padding: 10px 28px;
  font-size: 15px;
  border-radius: 100px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--primary);
  color: white;
  border: none;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(255, 36, 66, 0.2);
}

.generate-btn:hover {
  background: var(--primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(255, 36, 66, 0.3);
}

.generate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* 加载动画 */
.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
