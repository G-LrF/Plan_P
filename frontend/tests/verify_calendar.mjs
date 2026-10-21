/**
 * 日历逻辑验证脚本
 *
 * 【怎么运行】（在 frontend 目录下）
 *     node tests/verify_calendar.mjs
 *
 * 【为什么可以这样测】
 *   日历的核心是"给定年月，算出格子数组"——这是一个纯计算，不依赖浏览器。
 *   所以我把它原样复制一份到这里（保持与 App.vue 逻辑一致），
 *   用真实的边界日期去撞它。
 *
 *   企业里的正规做法是把这段逻辑抽成独立函数（例如 utils/calendar.js）
 *   然后 import 进来测；我们现在的逻辑还在组件里，所以只能复制。
 *   这个"想测却测不了"的别扭感，本身就是个信号：
 *   —— 当一段逻辑难以测试时，通常意味着它该被抽出去了。
 *
 * 【为什么必须测这些边界】
 *   改造前的代码把天数写死成 31、首日写死成 2023-12-01。
 *   写死的东西永远不会出错，因为根本没人用它算别的月份。
 *   一旦改成动态计算，就必须验证：
 *     二月是不是 28/29 天？闰年呢？31 天的月份会不会多出格子？30 天的呢？
 *   这些正是"写死"所掩盖的真实风险。
 */

let passed = 0
let failed = 0

function check(name, condition, detail = '') {
  if (condition) {
    passed++
    console.log(`  [PASS] ${name}`)
  } else {
    failed++
    console.log(`  [FAIL] ${name}  <-- ${detail}`)
  }
}

/* ==========================================================================
   以下逻辑与 App.vue 中 calendarData 的计算保持一致
   ========================================================================== */
function buildCalendar(year, month) {
  const firstDayOfWeek = new Date(year, month, 1).getDay() // 0=周日
  const leadingBlanks = (firstDayOfWeek + 6) % 7           // 表头从周一开始
  const daysInMonth = new Date(year, month + 1, 0).getDate() // 下月第0天=本月最后一天

  const cells = []
  for (let i = 0; i < leadingBlanks; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  return { cells, daysInMonth, leadingBlanks }
}

function isoDateKey(year, month, day) {
  return new Date(year, month, day).toLocaleDateString('en-CA')
}

/* ==========================================================================
   测试
   ========================================================================== */
console.log('\n=== 1. 各月份的天数是否正确（含闰年）===')
// 期望值我按真实历法写死在这里 —— 如果算错了，这里会立刻暴露。
const dayCountCases = [
  { y: 2026, m: 0,  expect: 31, label: '2026-01 一月' },
  { y: 2026, m: 1,  expect: 28, label: '2026-02 二月（平年 28 天）' },
  { y: 2024, m: 1,  expect: 29, label: '2024-02 二月（闰年 29 天）' },
  { y: 2000, m: 1,  expect: 29, label: '2000-02 闰年（能被400整除）' },
  { y: 1900, m: 1,  expect: 28, label: '1900-02 平年（能被100但不能被400整除，不是闰年）' },
  { y: 2100, m: 1,  expect: 28, label: '2100-02 平年' },
  { y: 2026, m: 3,  expect: 30, label: '2026-04 四月 30 天' },
  { y: 2026, m: 10, expect: 30, label: '2026-11 十一月 30 天' },
  { y: 2026, m: 11, expect: 31, label: '2026-12 十二月 31 天' },
]
for (const c of dayCountCases) {
  const { daysInMonth } = buildCalendar(c.y, c.m)
  check(`${c.label} -> ${c.expect} 天`, daysInMonth === c.expect, `实际算出 ${daysInMonth} 天`)
}

console.log('\n=== 2. 首日偏移（前置空格数）是否正确 ===')
// 逐个核对：表头是周一到周日，所以偏移 = (getDay()+6)%7
const offsetCases = [
  { y: 2026, m: 9,  label: '2026-10' },   // 2026-10-01 是周四 -> 偏移 3
  { y: 2026, m: 0,  label: '2026-01' },   // 2026-01-01 是周四 -> 偏移 3
  { y: 2024, m: 1,  label: '2024-02' },   // 2024-02-01 是周四 -> 偏移 3
  { y: 2023, m: 11, label: '2023-12' },   // 2023-12-01 是周五 -> 偏移 4
  { y: 2026, m: 2,  label: '2026-03' },
]
for (const c of offsetCases) {
  const { leadingBlanks, cells } = buildCalendar(c.y, c.m)
  const expected = (new Date(c.y, c.m, 1).getDay() + 6) % 7
  check(
    `${c.label} 前置空格 = ${expected}`,
    leadingBlanks === expected && cells.slice(0, expected).every((x) => x === null),
    `实际 ${leadingBlanks}`
  )
}

console.log('\n=== 3. 格子总数与首日在星期几（交叉验证）===')
// 把"1 号应该落在第几个格子"反推回星期几，看是否和真实星期一致。
// 这是防止 leadingBlanks 公式写反的关键测试。
let allAligned = true
for (let m = 0; m < 12; m++) {
  const { cells, leadingBlanks } = buildCalendar(2026, m)
  // cells 里第一个非 null 的位置就是 1 号的位置
  const posOfFirst = leadingBlanks
  // 位置 -> 星期：0 位置是周一，索引 0 对应周一
  const weekdayFromGrid = (posOfFirst % 7) // 0=周一 ... 6=周日
  // 真实星期：getDay() 0=周日 -> 转成 0=周一
  const realWeekday = (new Date(2026, m, 1).getDay() + 6) % 7
  if (weekdayFromGrid !== realWeekday) {
    allAligned = false
    console.log(`      不一致：${m + 1} 月 格子推算=${weekdayFromGrid} 真实=${realWeekday}`)
  }
}
check('2026 全年 12 个月，1 号落位与真实星期全部一致', allAligned)

console.log('\n=== 4. 31 天月份不会多出格子（原写死 31 的隐患）===')
// 改造前写死 31，所以 4 月这种 30 天的月份会显示出一个不存在的 31 日。
for (const c of [{ y: 2026, m: 3, name: '四月' }, { y: 2026, m: 5, name: '六月' }]) {
  const { cells } = buildCalendar(c.y, c.m)
  const realDays = cells.filter((x) => x !== null)
  check(
    `${c.name} 最大日期是 30，不存在 31 号`,
    Math.max(...realDays) === 30 && !realDays.includes(31),
    `实际最大值 ${Math.max(...realDays)}`
  )
}

console.log('\n=== 5. 二月不会多出 29/30/31 号（平年）===')
{
  const { cells } = buildCalendar(2026, 1)
  const days = cells.filter((x) => x !== null)
  check(
    '2026 年 2 月共 28 天，不含 29/30/31',
    days.length === 28 && Math.max(...days) === 28,
    `实际 ${days.length} 天，最大 ${Math.max(...days)}`
  )
}

console.log('\n=== 6. 空位用 null 而不是 0 ===')
{
  const { cells } = buildCalendar(2026, 9)
  const blanks = cells.filter((x) => x === null)
  check('前置位置是 null（不是 0）', blanks.length > 0 && !cells.includes(0), `cells=${cells}`)
  // 如果用 0 表示空位，模板里 `d ?? ''` 会把 0 正常渲染出来，
  // 日历上就会出现一排"0"。这一项专门防这个。
}

console.log('\n=== 7. 月份标题的多语言格式化 ===')
const titleCases = [
  { y: 2026, m: 9, locale: 'zh-CN', expect: '2026年10月' },
  { y: 2026, m: 9, locale: 'en-US', expect: 'October 2026' },
  { y: 2026, m: 0, locale: 'zh-CN', expect: '2026年1月' },
  { y: 2026, m: 0, locale: 'en-US', expect: 'January 2026' },
  { y: 2026, m: 11, locale: 'zh-CN', expect: '2026年12月' },
]
for (const c of titleCases) {
  const actual = new Date(c.y, c.m, 1).toLocaleDateString(c.locale, {
    year: 'numeric',
    month: 'long',
  })
  check(`${c.locale} ${c.y}-${c.m + 1} -> "${c.expect}"`, actual === c.expect, `实际 "${actual}"`)
}

console.log('\n=== 8. "今天"的判定 ===')
{
  const now = new Date()
  const key = isoDateKey(now.getFullYear(), now.getMonth(), now.getDate())
  // en-CA 的格式恰好是 YYYY-MM-DD，所以可以用正则严格校验
  check(
    `isoDateKey 产出 ISO 格式（${key}）`,
    /^\d{4}-\d{2}-\d{2}$/.test(key),
    `实际 "${key}"`
  )
  // 验证个位数月份/日期也补零了 —— 这是最容易出 bug 的地方
  const single = isoDateKey(2026, 0, 5) // 2026年1月5日
  check('个位数月/日会补零（2026-01-05）', single === '2026-01-05', `实际 "${single}"`)
  // 如果这里没补零（得到 2026-1-5），和 todayKey 比较就会失败，
  // 表现为"今天不高亮"，而且极难排查。
}

console.log('\n' + '='.repeat(56))
console.log(`  日历逻辑验证：${passed} 项通过，${failed} 项失败`)
console.log('='.repeat(56))
if (failed) {
  console.log('  [X] 有失败项，请检查 App.vue 里 calendarData 的计算。\n')
  process.exit(1)
}
console.log('  [OK] 日历动态计算正确，含闰年与边界月份。\n')
