<script setup>
/* ==========================================================================
   计划规划执行系统 · 仪表盘
   --------------------------------------------------------------------------
   【本文件现在承担什么角色】
     它是"展示层"：只负责两件事
       1. 调用 api/plan.js 把数据取回来
       2. 把数据渲染成界面，并把用户的操作转发给 api/plan.js
     它【不应该】直接出现 fetch，也不应该关心后端地址是什么。
     这条边界守住了，将来换后端、加登录，这个文件基本不用动。

   【本次改造的核心】把写死的假数据换成后端返回的真数据。
     改造前：const todayTasks = [写死的 3 条]        -> 别人打开页面看到的是同一份假数据
     改造后：const plans = ref([]) + loadPlans()    -> 数据来自 FastAPI 接口
   ========================================================================== */

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import {
  fetchPlans,
  createPlan,
  updatePlan,
  deletePlan,
} from './api/plan.js'

/* ============ 中英文文案词典 ============ */
const messages = {
  en: {
    brand: 'Timeyfi',
    nav_dashboard: 'Dashboard',
    nav_list: 'List',
    nav_calendar: 'Calendar',
    nav_messages: 'Messages',
    mylist: 'My list',
    workspace: 'Workspace',
    list_inbox: 'Inbox',
    list_work: 'Work',
    list_study: 'Study',
    list_health: 'Health',
    list_holiday: 'Holiday trip',
    ws_ui: 'UI Design',
    ws_team: 'A-team Class',
    search_placeholder: 'Search task',
    export_summary: 'Export summary',
    greeting: 'Good Morning, John',
    /* --- 与数据状态相关：会随接口返回结果变化 --- */
    stat_progress: '{done} of {total} done',
    src_live: 'Data from backend',
    src_mock: 'Demo data',
    /* --- 空状态 / 操作反馈 --- */
    empty_title: 'No plans yet',
    empty_hint: 'Create your first plan in the box below.',
    err_retry: 'Retry',
    loading: 'Loading...',
    action_done: 'Mark as done',
    action_undone: 'Mark as not done',
    action_delete: 'Delete',
    del_confirm: 'Delete this plan?',
    /* --- 界面上的固定文案 --- */
    up_next: 'Up next',
    upnext_meeting1: 'Design Team Meeting - Discuss new project wireframes',
    upnext_meeting2: 'Client Meeting - Review project updates and seek approval',
    upnext_note: 'This block is still demo data, not from the backend yet.',
    add_task: 'Add plan',
    tab_inbox: 'Inbox',
    tab_tomorrow: 'Tomorrow',
    tab_nextweek: 'Next week',
    tab_custom: 'Custom',
    task_placeholder: 'Write your plan...',
    today_task: 'My plans',
    cat_label: 'Plan No.',
    focus_timer: 'Focus timer',
    focus_none: 'No pending plan',
    mins: 'mins',
    start: 'Start',
    pause: 'Pause',
    /* 【本次改动】删掉了 month 和 wd_mon~wd_sun。
       原因见下方"日历"小节：月份和星期名现在都由 Date 对象 + 语言自动生成，
       不需要人工维护，也就不会再出现"改了年份忘了改字典"的问题。
       这里只保留星期全名的数组，用 slice(0, 3) 得到 Mon/Tue/... 这种缩写。 */
    wd_full: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
  },
  zh: {
    brand: 'Timeyfi',
    nav_dashboard: '仪表盘',
    nav_list: '列表',
    nav_calendar: '日历',
    nav_messages: '消息',
    mylist: '我的列表',
    workspace: '工作区',
    list_inbox: '收件箱',
    list_work: '工作',
    list_study: '学习',
    list_health: '健康',
    list_holiday: '假日旅行',
    ws_ui: 'UI 设计',
    ws_team: 'A-team 课堂',
    search_placeholder: '搜索任务',
    export_summary: '导出摘要',
    greeting: '早上好，John',
    stat_progress: '已完成 {done} / 共 {total} 项',
    src_live: '数据来自后端',
    src_mock: '演示数据',
    empty_title: '还没有任何计划',
    empty_hint: '在下面的输入框里创建第一条计划吧。',
    err_retry: '重试',
    loading: '加载中...',
    action_done: '标记为已完成',
    action_undone: '标记为未完成',
    action_delete: '删除',
    del_confirm: '确定要删除这条计划吗？',
    up_next: '接下来',
    upnext_meeting1: '设计团队会议 - 讨论新项目线框图',
    upnext_meeting2: '客户会议 - 审查项目进度并寻求批准',
    upnext_note: '此区块仍是演示数据，尚未接入后端。',
    add_task: '添加计划',
    tab_inbox: '收件箱',
    tab_tomorrow: '明天',
    tab_nextweek: '下周',
    tab_custom: '自定义',
    task_placeholder: '写下你的计划...',
    today_task: '我的计划',
    cat_label: '计划编号',
    focus_timer: '专注计时器',
    focus_none: '暂无未完成的计划',
    mins: '分钟',
    start: '开始',
    pause: '暂停',
    /* 【本次改动】同上：月份和星期不再需要人工维护。
       中文星期用 slice(0, 1) 得到"一/二/.../日"，正好是日历表头要的窄字符；
       英文用 slice(0, 3) 得到 Mon/Tue/...。
       同一份数据、两种裁剪方式，各自拿到该语言最合适的显示效果。 */
    wd_full: ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
  }
}

/* ============ 语言状态 ============ */
/**
 * 【本次改动】默认语言从 'en' 改为 'zh' —— 中文为主，英文可切换。
 *
 * 为什么把默认值抽成常量而不是直接写 ref('zh')？
 *   将来如果要做"记住用户上次选的语言"（存 localStorage），
 *   或者要支持第三种语言，改动点会集中在这一处，不会散落。
 *   小习惯，但能省事。
 */
const DEFAULT_LANG = 'zh'

/** 可切换的语言列表。加第三种语言时，这里和 messages 各加一项即可。 */
const SUPPORTED_LANGS = ['zh', 'en']

/** 每种语言在切换按钮上显示的名字（用它自己的母语写，是国际通行做法）。 */
const LANG_LABELS = { zh: '中文', en: 'English' }

const lang = ref(DEFAULT_LANG)

/**
 * 取文案。找不到 key 时返回 key 本身（而不是 undefined），
 * 这样界面上会直接显示 "stat_progress" 这种名字，
 * 你一眼就知道是漏了翻译 —— 比显示空白好排查得多。
 */
const t = (key, params) => {
  let text = messages[lang.value][key] ?? key
  // 简单的占位符替换：把 "{done}" 换成实际数字
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(`{${k}}`, v)
    }
  }
  return text
}

/**
 * 切换语言。
 * 【设计说明】按钮上显示的是"点击后会变成什么语言"，而不是"当前是什么语言"。
 *   当前是中文 -> 按钮显示 "English"（点了就切英文）
 *   当前是英文 -> 按钮显示 "中文"（点了就切中文）
 * 这是双语界面的通行做法；反过来会让用户以为按钮是用来标记当前语言的。
 */
function toggleLang() {
  lang.value = lang.value === 'zh' ? 'en' : 'zh'
}

/**
 * 计算"点击按钮后会切换到哪种语言"的名字。
 *
 * 【为什么要绕这一圈，不直接写 lang === 'zh' ? 'English' : '中文'】
 *   直接写死的话，"支持哪些语言"这件事就散落在模板里了。
 *   将来加第三种语言（比如日语），你得同时改 toggleLang 和模板两处，
 *   漏一处就会出现"按钮点了没反应"或"显示的语言名不对"。
 *   改成由 SUPPORTED_LANGS 数组驱动后，加语言只改数组和词典，
 *   切换逻辑和按钮文案都自动跟上。
 *
 * 【原理】indexOf 找到当前语言在数组里的位置，+1 取模得到下一个，
 * 循环切换。这是"环形数组"的常用写法。
 */
function nextLangLabel() {
  const index = SUPPORTED_LANGS.indexOf(lang.value)
  const next = SUPPORTED_LANGS[(index + 1) % SUPPORTED_LANGS.length]
  return LANG_LABELS[next]
}

/* ============ 导航与分类数据（纯展示，未接后端） ============ */
const navItems = [
  { key: 'dashboard', labelKey: 'nav_dashboard', icon: 'grid' },
  { key: 'list', labelKey: 'nav_list', icon: 'list' },
  { key: 'calendar', labelKey: 'nav_calendar', icon: 'calendar' },
  { key: 'messages', labelKey: 'nav_messages', icon: 'messages' }
]
const activeNav = ref('dashboard')

const myLists = [
  { key: 'inbox', labelKey: 'list_inbox', dot: '#60a5fa' },
  { key: 'work', labelKey: 'list_work', dot: '#a78bfa' },
  { key: 'study', labelKey: 'list_study', dot: '#f59e0b' },
  { key: 'health', labelKey: 'list_health', dot: '#34d399' },
  { key: 'holiday', labelKey: 'list_holiday', dot: '#fb7185' }
]

const workspaces = [
  { key: 'ui', labelKey: 'ws_ui' },
  { key: 'team', labelKey: 'ws_team' }
]

/* ==========================================================================
   ★ 核心改造区：计划数据（真数据）
   --------------------------------------------------------------------------
   下面这些 ref 就是"页面的状态"。Vue 的响应式规则：
     只要 ref 的值变了，用到它的界面部分会自动重新渲染。
   所以你不需要手动操作 DOM（不用 document.querySelector 那一套），
     只要 plans.value = [...]，界面自己就更新了。这就是 Vue 的核心价值。
   ========================================================================== */

/** 从后端拿回来的计划列表。初始是空数组，不是假数据。 */
const plans = ref([])

/** 是否正在请求中 —— 用来显示"加载中..."，避免用户以为页面卡死 */
const loading = ref(false)

/** 错误信息。非空时界面显示红色提示条。空字符串表示没有错误。 */
const errorMsg = ref('')

/** 是否成功从后端取到过数据 —— 用于顶部显示数据来源标记 */
const dataFromBackend = ref(false)

/**
 * 颜色映射：不同计划编号用不同颜色的标签。
 *
 * 【⚠️ 这是本轮明确记录的"设计债"，不是好设计，是临时方案】
 *   后端契约里 Plan 只有 id / title / content / status 四个字段，
 *   没有"分类"字段，所以这里拿 id 取余来分配颜色。
 *   正式做法是给表加 category 字段（例如 work / study / health），
 *   那是 P1-02 数据库设计阶段的事，那时字段才该真正增加。
 *   在此之前先用这个顶着，并且【不假装】它是真分类。
 */
const CATEGORY_COLORS = ['#60a5fa', '#a78bfa', '#f59e0b', '#34d399', '#fb7185']
function planColor(id) {
  const index = typeof id === 'number' ? id % CATEGORY_COLORS.length : 0
  return CATEGORY_COLORS[index]
}

/**
 * 把后端的 Plan 数据"翻译"成界面需要的形状。
 *
 * 【为什么要有这一层转换】
 *   后端字段名和界面需要的字段名不一定一致，而且这种不一致是会变的。
 *   把转换集中在一个 computed 里，将来后端加字段只改这一处，
 *   模板部分完全不用动。这叫"适配层"。
 *
 * 【后端字段 -> 界面用法 的对应关系】
 *   id      -> 计划编号标签、颜色
 *   title   -> 计划标题（主文案）
 *   content -> 计划内容（副文案）
 *   status  -> 0=未完成 / 1=已完成，决定勾选框样式
 */
const displayPlans = computed(() =>
  plans.value.map((plan) => ({
    id: plan.id,
    title: plan.title,
    content: plan.content,
    done: plan.status === 1,
    color: planColor(plan.id),
  }))
)

/** 已完成数量 */
const doneCount = computed(() => displayPlans.value.filter((p) => p.done).length)

/**
 * 专注计时器显示的目标计划：第一条未完成的计划。
 * 【小设计】没接后端之前这里写死成"整理桌面"，现在能真实反映你的待办，
 * 用户点"开始"时知道自己在专注哪件事。
 */
const focusTaskTitle = computed(() => {
  const firstPending = displayPlans.value.find((p) => !p.done)
  return firstPending ? firstPending.title : t('focus_none')
})

/* ==========================================================================
   与后端交互的四个动作
   --------------------------------------------------------------------------
   统一套路：调用 api 层 -> 看 ok -> 更新本地数据 或 显示错误
   ========================================================================== */

/** 从后端加载计划列表 */
async function loadPlans() {
  loading.value = true
  errorMsg.value = ''

  const res = await fetchPlans()

  if (res.ok) {
    // 接口返回结构是 { total, data }，我们真正要的是 data
    plans.value = res.data?.data ?? []
    dataFromBackend.value = true
  } else {
    errorMsg.value = res.message
  }

  loading.value = false
}

/** 新增计划 */
async function addPlan() {
  // 输入框是 UI 层的，所以在组件里取；
  // 但"能不能建"由后端说了算，我们不在前端重复写一遍校验规则。
  const title = newTask.value.trim()
  if (!title) return   // 空输入直接忽略，不发无意义的请求

  errorMsg.value = ''

  const res = await createPlan({
    title,
    // content 后端要求非空，而界面上只有一个输入框。
    // 临时把标题也当作内容；等接口加了独立的内容字段输入框再改。
    content: title,
  })

  if (res.ok) {
    // 【增量更新 vs 整体刷新】这里选择把新对象直接插到列表里。
    // 好处：不额外发一次请求，界面瞬间响应。
    // 坏处：如果后端在创建时改了别的字段，本地数据可能和真实数据不一致。
    // 企业里的取舍：数据一致性要求高的场景（如金融）宁可多请求一次做整体刷新。
    plans.value.push(res.data)
  } else {
    errorMsg.value = res.message
  }

  newTask.value = ''
}

/**
 * 切换某个计划的完成状态（未完成 <-> 已完成）
 *
 * 【为什么用 PUT 而不是 PATCH】
 *   后端现在只提供了 PUT。PUT 语义是"整体替换"，所以要把 title/content 一起传。
 *   更贴合语义的做法是后端加 PATCH /api/plans/{id}/status，只改状态一个字段。
 *   这属于接口设计优化，本轮不动，记在后续待办里。
 */
async function togglePlan(plan) {
  errorMsg.value = ''

  const res = await updatePlan(plan.id, {
    title: plan.title,
    content: plan.content,
    status: plan.done ? 0 : 1,   // 取反
  })

  if (res.ok) {
    // 用后端返回的对象更新本地，保证界面显示的就是服务端真实状态
    const index = plans.value.findIndex((p) => p.id === plan.id)
    if (index !== -1) plans.value[index] = res.data
  } else {
    errorMsg.value = res.message
  }
}

/** 删除计划 */
async function removePlan(plan) {
  // 【二次确认】删除不可逆，必须让用户确认。
  // 这是最基本的安全感设计：企业系统里所有破坏性操作都要确认。
  // （正式产品会用自己的弹窗组件而不是浏览器原生 confirm，此处从简）
  if (!window.confirm(`${t('del_confirm')}\n\n${plan.title}`)) return

  errorMsg.value = ''

  const res = await deletePlan(plan.id)

  if (res.ok) {
    // filter 生成一个不包含该 id 的新数组。
    // 【为什么不用 splice】filter 是函数式写法，意图更明确（"留下不符合条件的"），
    // 也不容易因为索引算错而删错对象。
    plans.value = plans.value.filter((p) => p.id !== plan.id)
  } else {
    errorMsg.value = res.message
  }
}

/** 用户点"重试"时重新加载 */
function retryLoad() {
  loadPlans()
}

/* ============ 添加计划的输入框与分页签 ============ */
const addTabs = ['tab_inbox', 'tab_tomorrow', 'tab_nextweek', 'tab_custom']
const activeAddTab = ref('tab_inbox')
const newTask = ref('')
/* 【已知限制】这四个分页签目前只是视觉切换，没有真正按分类过滤 ——
   因为后端还没有 category 字段。等数据库阶段加了字段再让它生效。
   现在【不假装它有效】，只作为界面保留。 */

/* ============ 即将进行（Up next）：仍是演示数据 ============ */
const upNext = [
  { titleKey: 'upnext_meeting1', time: '11:30 AM - 01:00 PM', tag: '10:00 AM' },
  { titleKey: 'upnext_meeting2', time: '03:00 PM - 05:00 PM', tag: '12:00 PM' }
]

/* ==========================================================================
   日历 —— 按当前月份动态生成
   --------------------------------------------------------------------------
   【本次改动的核心】
     改造前：月份写死 December 2023，格子数写死 31，首日写死按 2023-12-01 算。
             结果是一个"永远停在 2023 年 12 月"的假日历。
     改造后：年月来自 Date 对象，格子数按当月真实天数算，能被翻页。

   【真实案例 · 为什么写死的日期是隐患而不是小事】
     这类"写死的演示数据"最危险的地方不是难看，而是：
       1. 上线后会被人当成 bug 报上来（"日历怎么停在 2023 年？"）
       2. 更要命的是它掩盖了真实逻辑的缺失 —— 格子数写死 31，
          二月跑起来就会显示不存在的 29/30/31 日，而这个错误在
          演示数据的掩护下永远不会暴露。
     所以动态化的价值不只是"显示正确的月份"，而是让真实逻辑第一次被真正跑起来。
   ========================================================================== */

/* 当前显示的年份和月份。
   【为什么用 ref 而不是普通变量】
     它们是会被改变的（将来做月份翻页时），用 ref 才能触发界面更新。
     现在虽然只读当前月份，但用 ref 定义好，加翻页时不用改造结构。
   【注意】month 用 0~11 表示，这是 JavaScript Date 的规定（0 = 一月）。
     这个"从 0 开始"是新手最容易踩的坑之一，看到 11 不要以为它代表 11 月。 */
const today = new Date()
const viewYear = ref(today.getFullYear())
const viewMonth = ref(today.getMonth())

/**
 * 日期格式化用的语言标识。
 * 【为什么要这个映射】toLocaleDateString 需要的是语言标识（zh-CN / en-US），
 * 而界面语言标识是简写（zh / en）。两者不是一回事，需要显式对应。
 * 用数组形式返回多个候选，浏览器会挑选第一个它认识的，
 * 这样即使某个环境不支持 zh-CN 也能优雅降级，不会显示成乱码或英文缩写。
 */
const dateLocale = computed(() => (lang.value === 'zh' ? ['zh-CN', 'zh'] : ['en-US', 'en']))

/**
 * 月份标题，例如 "2026年10月" / "October 2026"。
 * 【关键点】交给浏览器内置的 Intl 能力去生成，而不是我们手工拼字符串。
 *   手工拼的问题：中文是"2026年10月"，英文是"October 2026"，
 *   语序完全不同，各国还有自己的写法（有的月份在前、有的在后）。
 *   自己拼字符串等于要维护一份"每种语言的日期格式规则表"，做不完。
 *   toLocaleDateString 直接调用系统语言库，免费拿到正确结果。
 */
const monthLabel = computed(() =>
  new Date(viewYear.value, viewMonth.value, 1).toLocaleDateString(dateLocale.value, {
    year: 'numeric',
    month: 'long',
  })
)

/**
 * 日历格子的数据源。
 * 【返回一个对象而不是数组，是为了让模板能拿到格子总数（用于断言和网格高度）】
 *   null 表示这个位置是上月剩下的空格 —— 不是"0 号"，所以必须用 null 表示空。
 *   如果用 0，模板里 `d ?? ''` 会把 0 正常渲染出来，日历上就多出一堆 0。
 */
const calendarData = computed(() => {
  // 第 1 天是星期几（0 = 周日，1 = 周一）
  const firstDayOfWeek = new Date(viewYear.value, viewMonth.value, 1).getDay()

  // 算第一行需要几个前置空格。
  // 日历表头是"周一到周日"（中文习惯），而 getDay() 里 0 代表周日、
  // 周日排在最后。所以要把 0 映射成 6，其余减 1：(n + 6) % 7
  //   周日(0) -> 6    周一(1) -> 0    周六(6) -> 5
  const leadingBlanks = (firstDayOfWeek + 6) % 7

  // ★ 当月天数由 Date 自动算出，不用写死 31。
  //   原理：下个月的第 0 天 = 这个月的最后一天。
  //   比如 new Date(2026, 2, 0) —— 3 月 0 日 —— 就是 2 月的最后一天（28 或 29）。
  //   这个技巧能自动处理闰年，比自己判断"是不是闰年"可靠得多。
  const daysInMonth = new Date(viewYear.value, viewMonth.value + 1, 0).getDate()

  const cells = []
  for (let i = 0; i < leadingBlanks; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  return { cells, daysInMonth, leadingBlanks }
})

/** 兼容写法：模板里直接要格子数组时用它 */
const calendarDays = computed(() => calendarData.value.cells)

/** 星期表头。中文取首字（一/二/…），英文取前三字母（Mon/Tue/…）。 */
const weekdayLabels = computed(() => {
  const full = messages[lang.value].wd_full
  return lang.value === 'zh' ? full.map((w) => w.slice(0, 1)) : full.map((w) => w.slice(0, 3))
})

/**
 * 今天的日期字符串，用于在日历上高亮"今天"。
 * 【为什么要用 en-CA 这个看起来奇怪的 locale】
 *   因为 en-CA（加拿大英语）的日期格式恰好是 YYYY-MM-DD，也就是 ISO 格式。
 *   这样拼出来的 key 可以直接和格子日期做字符串比较，不用手动补零：
 *     new Date(...).toLocaleDateString('en-CA')  ->  "2026-10-12"
 *   如果自己拼 `${y}-${m}-${d}`，就必须处理 "2026-10-5" vs "2026-10-05" 的补零问题，
 *   一不小心比较就失败。这是个很实用的小技巧。
 */
function isoDateKey(year, month, day) {
  return new Date(year, month, day).toLocaleDateString('en-CA')
}

/** 今天的 key，只在初始化时算一次 */
const todayKey = isoDateKey(today.getFullYear(), today.getMonth(), today.getDate())

/** 判断某个格子是不是今天 */
function isToday(day) {
  if (day === null) return false
  return isoDateKey(viewYear.value, viewMonth.value, day) === todayKey
}

/* 【已删除】busyDates = [7, 11, 15, 22, 27]
   那是一组写死日期，用来在日历上画"有日程"的小圆点。
   但它标的日子是凭空编的，跟任何真实数据都没关系 —— 典型的假装饰。
   而且它按"日期数字"匹配，不分年月，所以每个月都会亮同样几个日子，纯属误导。
   现在改为高亮"今天"：这个信息是真实且有用的。
   真正的"哪些天有计划"要等 plans 表有 due_date 字段之后才能做（P1-02）。 */

/* ============ 专注计时器（纯前端，不涉及后端） ============ */
/* 【为什么计时器不放后端】
   它是"界面交互状态"，关掉页面就没意义了，不需要持久化。
   判断"数据该放前端还是后端"的一个简单标准：
     用户关掉页面还需要保留吗？需要 -> 后端；不需要 -> 前端。
   注意：如果将来要做"番茄钟历史统计"，那就要存到后端了。 */
const focusMinutes = ref(30)
const remainingSec = ref(30 * 60)
const timerRunning = ref(false)
let timerId = null

const focusTime = computed(() => {
  const m = Math.floor(remainingSec.value / 60)
  const s = remainingSec.value % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

function toggleTimer() {
  if (timerRunning.value) {
    timerRunning.value = false
    clearInterval(timerId)
    timerId = null
    return
  }
  if (remainingSec.value <= 0) remainingSec.value = focusMinutes.value * 60
  timerRunning.value = true
  timerId = setInterval(() => {
    remainingSec.value -= 1
    if (remainingSec.value <= 0) {
      remainingSec.value = 0
      timerRunning.value = false
      clearInterval(timerId)
      timerId = null
    }
  }, 1000)
}

/* ============ 生命周期 ============ */
/**
 * onMounted：组件挂载到页面后执行一次。
 * 【为什么把加载数据放这里，而不是直接在 setup 顶层写】
 *   直接写在顶层也能跑，但那是"在渲染过程中发起副作用"，
 *   数据回来时组件可能还没准备好。放在 onMounted 里语义清晰：
 *   "界面已经出现在屏幕上了，现在去取数据"。
 *   这是 Vue 官方推荐的取数据位置。
 */
onMounted(() => {
  loadPlans()
})

onBeforeUnmount(() => {
  // 【为什么要清掉定时器】组件销毁后定时器还在跑，就会一直占内存，
  // 并试图更新已不存在的界面。在单页应用里切来切去，
  // 这类"没清理的定时器/监听器"是内存泄漏的头号来源。
  if (timerId) clearInterval(timerId)
})
</script>

<template>
  <div class="app">
    <!-- ===== 左侧边栏 ===== -->
    <aside class="sidebar">
      <div class="logo">
        <div class="logo-mark">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 10h10M4 14h13"/></svg>
        </div>
        <span class="logo-name">{{ t('brand') }}</span>
      </div>

      <nav class="nav">
        <a
          v-for="item in navItems"
          :key="item.key"
          class="nav-item"
          :class="{ active: activeNav === item.key }"
          href="#"
          @click.prevent="activeNav = item.key"
        >
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <template v-if="item.icon === 'grid'"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></template>
            <template v-else-if="item.icon === 'list'"><path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/></template>
            <template v-else-if="item.icon === 'calendar'"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/></template>
            <template v-else=""><path d="M21 12a8 8 0 0 1-8 8H4l3-3a8 8 0 1 1 14-5Z"/></template>
          </svg>
          {{ t(item.labelKey) }}
        </a>
      </nav>

      <div class="side-group">
        <div class="side-head">
          <span>{{ t('mylist') }}</span>
          <button class="add-btn" aria-label="add list">+</button>
        </div>
        <ul class="side-list">
          <li v-for="list in myLists" :key="list.key">
            <a href="#">
              <span class="dot" :style="{ background: list.dot }"></span>{{ t(list.labelKey) }}
            </a>
          </li>
        </ul>
      </div>

      <div class="side-group">
        <div class="side-head">
          <span>{{ t('workspace') }}</span>
          <button class="add-btn" aria-label="add workspace">+</button>
        </div>
        <ul class="side-list">
          <li v-for="ws in workspaces" :key="ws.key">
            <a href="#"><span class="dot ws-dot"></span>{{ t(ws.labelKey) }}</a>
          </li>
        </ul>
      </div>
    </aside>

    <!-- ===== 右侧主体 ===== -->
    <div class="main">
      <!-- 顶部导航 -->
      <header class="topbar">
        <div class="search-box">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>
          <input type="text" :placeholder="t('search_placeholder')" />
        </div>
        <div class="top-actions">
          <button class="lang-btn" @click="toggleLang">{{ nextLangLabel() }}</button>
          <button class="export-btn">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3v12M7 10l5 5 5-5M4 21h16"/></svg>
            {{ t('export_summary') }}
          </button>
          <span class="icon-btn" aria-label="notifications">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0"/></svg>
            <i class="notif-dot"></i>
          </span>
          <span class="avatar">J</span>
        </div>
      </header>

      <!-- 主内容区（两栏） -->
      <div class="main-body">
        <div class="col-main">
          <!-- 欢迎板块 -->
          <section class="welcome-card">
            <div class="welcome-text">
              <h1>{{ t('greeting') }}</h1>
              <p>
                <!-- 这里的数字是真实统计结果，来自后端返回的数据 -->
                {{ t('stat_progress', { done: doneCount, total: displayPlans.length }) }}
                <!-- 数据来源标记：让你一眼看出页面到底连没连上后端 -->
                <span class="src-badge" :class="{ live: dataFromBackend }">
                  {{ dataFromBackend ? t('src_live') : t('src_mock') }}
                </span>
              </p>
            </div>
            <div class="welcome-art">
              <svg viewBox="0 0 80 70" width="92" height="78" fill="none">
                <circle cx="62" cy="16" r="12" fill="#d7f5e3"/>
                <circle cx="18" cy="22" r="4" fill="#bce7cf"/>
                <circle cx="70" cy="6" r="3" fill="#bce7cf"/>
                <path d="M14 34c14-16 30-20 42-8 8 8 4 22-10 24H22c-8 0-8-16-8-16Z" fill="#34d399"/>
                <path d="M22 34c6-14 16-24 30-22M28 50c6-10 18-12 26-6" stroke="#a3e635" stroke-width="2" stroke-linecap="round"/>
                <path d="M18 68h44" stroke="#d1d5db" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </div>
          </section>

          <!-- 错误提示条：只有出错时才显示 -->
          <div v-if="errorMsg" class="error-bar">
            <span class="error-icon">!</span>
            <!-- white-space: pre-line 让 \n 能真正换行，否则提示会挤成一行 -->
            <p class="error-text">{{ errorMsg }}</p>
            <button class="retry-btn" @click="retryLoad">{{ t('err_retry') }}</button>
          </div>

          <!-- Up next -->
          <section class="card upnext">
            <h2 class="card-title">{{ t('up_next') }}</h2>
            <div v-for="(meet, i) in upNext" :key="i" class="meet-item">
              <div class="meet-time">
                <span class="meet-chip">{{ meet.tag }}</span>
                <p class="meet-range">{{ meet.time }}</p>
              </div>
              <div class="meet-info">
                <h3>{{ t(meet.titleKey) }}</h3>
              </div>
            </div>
            <!-- 诚实标注：这块还没接后端，避免你和别人误以为整个页面都联调完了 -->
            <p class="demo-note">{{ t('upnext_note') }}</p>
          </section>

          <!-- 添加计划 -->
          <section class="add-task">
            <h2 class="card-title">{{ t('add_task') }}</h2>
            <div class="add-row">
              <ul class="add-tabs">
                <li
                  v-for="tab in addTabs"
                  :key="tab"
                  :class="{ active: activeAddTab === tab }"
                  @click="activeAddTab = tab"
                >{{ t(tab) }}</li>
              </ul>
              <div class="add-input">
                <input
                  v-model="newTask"
                  type="text"
                  :placeholder="t('task_placeholder')"
                  @keyup.enter="addPlan"
                />
                <!-- @click 绑定的是 addPlan：点一下就会真的发 POST 请求到后端 -->
                <button class="add-task-btn" @click="addPlan">+</button>
              </div>
            </div>
          </section>

          <!-- 我的计划 -->
          <section class="card today">
            <h2 class="card-title">{{ t('today_task') }}</h2>

            <!-- 状态一：正在加载 -->
            <p v-if="loading" class="state-text">{{ t('loading') }}</p>

            <!-- 状态二：加载完成但一条数据都没有 -->
            <!-- 【为什么要专门做空状态】界面空白会让用户以为程序坏了。
                 明确告诉他"还没数据 + 下一步做什么"，是基本的体验设计。 -->
            <div v-else-if="displayPlans.length === 0" class="empty-state">
              <p class="empty-title">{{ t('empty_title') }}</p>
              <p class="empty-hint">{{ t('empty_hint') }}</p>
            </div>

            <!-- 状态三：正常渲染数据 -->
            <ul v-else class="task-list">
              <li
                v-for="plan in displayPlans"
                :key="plan.id"
                class="task-item"
                :class="{ done: plan.done }"
              >
                <!-- 点击圆圈切换完成状态；:title 是鼠标悬停提示，说明这个按钮干什么 -->
                <button
                  class="task-check"
                  :class="{ checked: plan.done }"
                  :title="plan.done ? t('action_undone') : t('action_done')"
                  @click="togglePlan(plan)"
                ></button>

                <div class="task-body">
                  <h3>{{ plan.title }}</h3>
                  <span class="task-cat" :style="{ background: plan.color + '1f', color: plan.color }">
                    {{ plan.content }}
                  </span>
                </div>

                <span class="task-id">{{ t('cat_label') }} {{ plan.id }}</span>

                <!-- 删除按钮：@click.stop 阻止事件冒泡，避免误触发其他点击行为 -->
                <button class="del-btn" :title="t('action_delete')" @click.stop="removePlan(plan)">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13"/></svg>
                </button>
              </li>
            </ul>
          </section>
        </div>

        <!-- 右栏：日历 + 专注计时器 -->
        <div class="col-right">
          <section class="card calendar">
            <div class="cal-head">
              <!-- 月份标题现在是动态生成的："2026年10月" / "October 2026" -->
              <h2 class="card-title">{{ monthLabel }}</h2>
              <!-- 【占位】这个 ‹ 目前还不能点。想做成月份翻页时，
                   给它绑 @click="viewMonth--"（并处理跨年进位）即可，
                   因为 viewYear / viewMonth 已经改成 ref 了，界面会自动更新。 -->
              <span class="cal-nav">‹</span>
            </div>
            <div class="cal-grid">
              <!-- 【:key 为什么用索引而不是星期文字】
                   中文星期取首字后会出现重复：星期三和星期六都是"三"和"六"，
                   星期五和星期日… 实际上星期三→"三"、星期六→"六" 不重复，
                   但"星期一"→"一" 和 "星期日"→"日" 看似不重复，
                   可一旦改用别的裁剪方式就会撞车。
                   用索引做 key 永远唯一，是这类渲染的稳妥写法。
                   【关于 :key 的重要性】Vue 靠 key 判断"哪个元素是哪个"，
                   key 重复会导致更新错位（比如点了周三却高亮了周六）。 -->
              <span
                v-for="(w, idx) in weekdayLabels"
                :key="'wd-' + idx"
                class="cal-wd"
              >{{ w }}</span>

              <span
                v-for="(d, idx) in calendarDays"
                :key="idx"
                class="cal-day"
                :class="{ muted: d === null, busy: isToday(d) }"
              >{{ d ?? '' }}</span>
            </div>
          </section>

          <section class="card focus">
            <h2 class="card-title">{{ t('focus_timer') }}</h2>
            <!-- 现在显示的是你第一条未完成的计划，而不是写死的文案 -->
            <p class="focus-task">{{ focusTaskTitle }}</p>
            <div class="focus-ring">
              <div class="focus-circle">
                <div class="focus-time">{{ focusTime }}</div>
              </div>
              <p class="focus-label">{{ focusMinutes }} {{ t('mins') }}</p>
            </div>
            <button class="start-btn" :class="{ running: timerRunning }" @click="toggleTimer">
              {{ timerRunning ? t('pause') : t('start') }}
            </button>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>
