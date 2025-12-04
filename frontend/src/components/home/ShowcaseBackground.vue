<template>
  <!-- 原创插画网格轮播背景 -->
  <div class="showcase-background" :class="{ 'is-ready': isReady }">
    <div class="showcase-grid" :style="{ transform: `translateY(-${scrollOffset}px)` }">
      <div 
        v-for="(card, index) in mockCards" 
        :key="index" 
        class="showcase-item"
        :class="card.colorClass"
      >
        <div class="card-content">
          <div class="card-icon">{{ card.icon }}</div>
          <div class="card-title">{{ card.title }}</div>
          <div class="card-meta">
            <div class="card-likes">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" class="heart-icon"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
              {{ card.likes }}
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="showcase-overlay"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 背景卡片数据接口
 */
interface MockCard {
  icon: string
  title: string
  colorClass: string
  likes: string
}

// 滚动偏移量
const scrollOffset = ref(0)
// 是否准备好显示
const isReady = ref(false)
// 卡片列表
const mockCards = ref<MockCard[]>([])

// 滚动定时器
let scrollInterval: ReturnType<typeof setInterval> | null = null

// 预设数据池
const EMOJIS = ['💄', '☕️', '🏕️', '📷', '🧘‍♀️', '👗', '🥘', '🎨', '💅', '📖', '🐶', '👜', '🏖️', '🏃‍♀️', '🎓', '💐']
const TITLES = [
  '沉浸式护肤', '周末探店', '精致露营', 'OOTD分享', '减脂餐打卡', 
  '初秋穿搭', '平价好物', '美甲灵感', '书单分享', '铲屎官日常',
  '旅行攻略', '职场干货', '摄影技巧', '家居改造', 'VLOG日常',
  '宝藏店铺', '显白发色', '约会妆容', '自律生活', '好物开箱'
]
const COLORS = ['bg-red', 'bg-yellow', 'bg-green', 'bg-purple', 'bg-orange', 'bg-blue']

/**
 * 生成模拟卡片数据
 * 生成足够多的卡片以填满屏幕并支持滚动
 */
function generateMockCards() {
  const cards: MockCard[] = []
  const count = 66 // 11列 * 6行，足够覆盖且循环
  
  for (let i = 0; i < count; i++) {
    cards.push({
      icon: EMOJIS[Math.floor(Math.random() * EMOJIS.length)],
      title: TITLES[Math.floor(Math.random() * TITLES.length)],
      colorClass: COLORS[Math.floor(Math.random() * COLORS.length)],
      likes: (Math.floor(Math.random() * 90) + 10) + (Math.random() > 0.5 ? 'k' : '')
    })
  }
  
  // 复制三份实现无缝滚动
  mockCards.value = [...cards, ...cards, ...cards]
  isReady.value = true
}

/**
 * 启动滚动动画
 */
function startScrollAnimation() {
  // 计算网格总高度（每行约180px：164px卡片 + 16px间距）
  // 原始数据有6行
  const rowHeight = 180
  const totalRows = 6 
  const sectionHeight = totalRows * rowHeight

  scrollInterval = setInterval(() => {
    scrollOffset.value += 0.6 // 极慢速滚动
    
    // 滚动到第二组末尾时重置到第一组开始位置
    if (scrollOffset.value >= sectionHeight) {
      scrollOffset.value = 0
    }
  }, 30)
}

onMounted(() => {
  generateMockCards()
  // 稍微延迟启动滚动，避免卡顿
  setTimeout(() => {
    startScrollAnimation()
  }, 100)
})

onUnmounted(() => {
  if (scrollInterval) {
    clearInterval(scrollInterval)
  }
})
</script>

<style scoped>
/* 背景容器 */
.showcase-background {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100vh;
  z-index: -1;
  overflow: hidden;
  opacity: 0;
  transition: opacity 0.8s ease-out;
  background: #FDFDFD;
}

.showcase-background.is-ready {
  opacity: 1;
}

/* 图片网格 */
.showcase-grid {
  display: grid;
  grid-template-columns: repeat(11, 1fr);
  gap: 16px;
  padding: 20px;
  width: 100%;
  will-change: transform;
}

/* 卡片样式 */
.showcase-item {
  width: 100%;
  aspect-ratio: 3 / 4;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
  position: relative;
  transition: transform 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(0,0,0,0.02);
}

/* 颜色变体 - 柔和的马卡龙色系 */
.bg-red { background: linear-gradient(135deg, #FFF0F2 0%, #FFD6E0 100%); }
.bg-yellow { background: linear-gradient(135deg, #FFFBE6 0%, #FFF1B8 100%); }
.bg-green { background: linear-gradient(135deg, #F6FFED 0%, #D9F7BE 100%); }
.bg-purple { background: linear-gradient(135deg, #F9F0FF 0%, #EFDBFF 100%); }
.bg-orange { background: linear-gradient(135deg, #FFF7E6 0%, #FFE7BA 100%); }
.bg-blue { background: linear-gradient(135deg, #E6F7FF 0%, #BAE7FF 100%); }

.card-content {
  text-align: center;
  width: 100%;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  justify-content: center;
}

.card-icon {
  font-size: 48px;
  margin-bottom: 12px;
  filter: drop-shadow(0 4px 8px rgba(0,0,0,0.06));
  transition: transform 0.3s ease;
}

.showcase-item:hover .card-icon {
  transform: scale(1.1);
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: #555;
  margin-bottom: 8px;
  background: rgba(255,255,255,0.6);
  padding: 4px 10px;
  border-radius: 100px;
  white-space: nowrap;
}

.card-meta {
  margin-top: auto;
  width: 100%;
  display: flex;
  justify-content: flex-end;
}

.card-likes {
  font-size: 11px;
  color: #888;
  display: flex;
  align-items: center;
  gap: 3px;
  font-weight: 600;
}

.heart-icon {
  color: #FF2442;
}

/* 毛玻璃遮罩层 */
.showcase-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    to bottom,
    rgba(255, 255, 255, 0.9) 0%,
    rgba(255, 255, 255, 0.75) 40%,
    rgba(255, 248, 248, 0.92) 100%
  );
  backdrop-filter: blur(3px);
}

/* 响应式布局 */
@media (max-width: 768px) {
  .showcase-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    padding: 12px;
  }
  
  .card-icon {
    font-size: 32px;
  }
  
  .card-title {
    font-size: 12px;
    padding: 2px 8px;
  }
}
</style>
