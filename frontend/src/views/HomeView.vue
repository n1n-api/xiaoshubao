<template>
  <div class="container home-container">
    <!-- 图片网格轮播背景 -->
    <ShowcaseBackground />

    <!-- Hero Area -->
    <div class="hero-section">
      <div class="hero-content">
        <div class="brand-pill">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>
          拒绝无效更新，10秒生成“爆款笔记”
        </div>
        <h1 class="page-title">
          懂流量的AI<br/>
          更懂你的<span class="highlight-text">创作焦虑</span>
        </h1>
        <p class="page-subtitle">
          把时间花在生活上，写笔记交给小薯宝。不用懂设计，也不用熬夜写，一键生成“博主感”满满的优质笔记。
        </p>
      </div>

      <!-- 主题输入组合框 -->
      <ComposerInput
        ref="composerRef"
        v-model="topic"
        :loading="loading"
        @generate="handleGenerate"
        @imagesChange="handleImagesChange"
      />
    </div>
    
    <!-- 痛点直击板块 -->
    <div class="features-section">
      <div class="feature-card soft-red">
        <div class="feature-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
        </div>
        <h3>“标题废”救星</h3>
        <p>还在写“好用的护肤品”？太土了！小薯宝帮你改成“<strong>妈耶！熬夜党直接锁死！这瓶精华我是跪着推的😭</strong>”。</p>
      </div>
      
      <div class="feature-card soft-yellow">
        <div class="feature-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
        </div>
        <h3>“封面丑”终结者</h3>
        <p>内容满分，封面劝退？AI 自动匹配高颜值、杂志感封面，让路人忍不住点进来。</p>
      </div>
      
      <div class="feature-card soft-green">
        <div class="feature-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path></svg>
        </div>
        <h3>“断更”治疗仪</h3>
        <p>没有灵感？随便扔个词，我们还你一篇万赞潜力的种草文，彻底告别灵感枯竭。</p>
      </div>
    </div>

    <!-- 版权信息 -->
    <div class="page-footer">
      <div class="footer-copyright">
        © 2025 <a href="https://xiaoshubao.me" target="_blank" rel="noopener noreferrer">小薯宝</a>
      </div>
      <div class="footer-license">
        Licensed under <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-NC-SA 4.0</a>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-toast">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { generateOutline } from '../api'

// 引入组件
import ShowcaseBackground from '../components/home/ShowcaseBackground.vue'
import ComposerInput from '../components/home/ComposerInput.vue'

const router = useRouter()
const store = useGeneratorStore()

// 状态
const topic = ref('')
const loading = ref(false)
const error = ref('')
const composerRef = ref<InstanceType<typeof ComposerInput> | null>(null)

// 上传的图片文件
const uploadedImageFiles = ref<File[]>([])

/**
 * 处理图片变化
 */
function handleImagesChange(images: File[]) {
  uploadedImageFiles.value = images
}

/**
 * 生成大纲
 */
async function handleGenerate() {
  if (!topic.value.trim()) return

  loading.value = true
  error.value = ''

  try {
    const imageFiles = uploadedImageFiles.value

    const result = await generateOutline(
      topic.value.trim(),
      imageFiles.length > 0 ? imageFiles : undefined
    )

    if (result.success && result.pages) {
      store.setTopic(topic.value.trim())
      store.setOutline(result.outline || '', result.pages)
      store.recordId = null // 先重置

      // 保存用户上传的图片到 store
      if (imageFiles.length > 0) {
        store.userImages = imageFiles
      } else {
        store.userImages = []
      }

      // 立即创建历史记录（草稿状态）
      try {
        const { createHistory } = await import('../api')
        const historyResult = await createHistory(topic.value.trim(), {
          raw: result.outline || '',
          pages: result.pages
        })
        
        if (historyResult.success && historyResult.record_id) {
          store.recordId = historyResult.record_id
          console.log('自动创建历史记录成功:', historyResult.record_id)
        }
      } catch (e) {
        console.error('自动创建历史记录失败:', e)
        // 不阻断跳转
      }

      // 清理 ComposerInput 的预览
      composerRef.value?.clearPreviews()
      uploadedImageFiles.value = []

      router.push('/outline')
    } else {
      error.value = result.error || '生成大纲失败'
    }
  } catch (err: any) {
    error.value = err.message || '网络错误，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.home-container {
  max-width: 1100px;
  padding-top: 10px;
  position: relative;
  z-index: 1;
}

/* Hero Section */
.hero-section {
  text-align: center;
  margin-bottom: 40px;
  padding: 50px 60px;
  animation: fadeIn 0.6s ease-out;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 24px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
  backdrop-filter: blur(10px);
}

.hero-content {
  margin-bottom: 42px;
}

.brand-pill {
  display: inline-flex;
  align-items: center;
  padding: 8px 20px;
  background: rgba(255, 36, 66, 0.08);
  color: var(--primary);
  border-radius: 100px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 24px;
  letter-spacing: 0.5px;
}

.page-title {
  font-size: 48px;
  line-height: 1.2;
  font-weight: 800;
  color: var(--text-main);
  margin-bottom: 20px;
  letter-spacing: -1px;
}

.highlight-text {
  background: linear-gradient(120deg, #ff9a9e 0%, #fecfef 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  position: relative;
}

.highlight-text::after {
  content: '';
  position: absolute;
  bottom: 4px;
  left: 0;
  width: 100%;
  height: 8px;
  background: rgba(255, 36, 66, 0.1);
  z-index: -1;
  border-radius: 4px;
}

.page-subtitle {
  font-size: 18px;
  color: var(--text-sub);
  margin-top: 12px;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
  line-height: 1.6;
}

/* Features Section */
.features-section {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  margin-bottom: 60px;
  padding: 0 20px;
  animation: slideUp 0.6s ease-out 0.2s backwards;
}

.feature-card {
  background: white;
  border-radius: 20px;
  padding: 32px 24px;
  text-align: center;
  transition: all 0.3s ease;
  border: 1px solid rgba(0,0,0,0.03);
  box-shadow: 0 4px 20px rgba(0,0,0,0.02);
}

.feature-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.06);
}

.feature-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  font-size: 24px;
}

.feature-card.soft-red .feature-icon { background: #FFF0F2; color: var(--primary); }
.feature-card.soft-yellow .feature-icon { background: #FFF9C4; color: #F57F17; }
.feature-card.soft-green .feature-icon { background: #E8F5E9; color: #2E7D32; }

.feature-card h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-main);
  margin-bottom: 12px;
}

.feature-card p {
  font-size: 14px;
  color: var(--text-sub);
  line-height: 1.6;
}

/* Page Footer */
.page-footer {
  text-align: center;
  padding: 24px 0 16px;
  margin-top: 20px;
}

.footer-copyright {
  font-size: 15px;
  color: #333;
  font-weight: 500;
  margin-bottom: 6px;
}

.footer-copyright a {
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
}

.footer-copyright a:hover {
  text-decoration: underline;
}

.footer-license {
  font-size: 13px;
  color: #999;
}

.footer-license a {
  color: #666;
  text-decoration: none;
}

.footer-license a:hover {
  color: var(--primary);
}

/* Error Toast */
.error-toast {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  background: #FF4D4F;
  color: white;
  padding: 12px 24px;
  border-radius: 50px;
  box-shadow: 0 8px 24px rgba(255, 77, 79, 0.3);
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 1000;
  animation: slideUp 0.3s ease-out;
}

/* Animations */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Responsive */
@media (max-width: 768px) {
  .features-section {
    grid-template-columns: 1fr;
  }
  
  .page-title {
    font-size: 36px;
  }
  
  .hero-section {
    padding: 30px 20px;
  }
}
</style>
