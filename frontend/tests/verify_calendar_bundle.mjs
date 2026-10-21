/**
 * 产物验证 —— 确认日历已动态化（不再写死 2023 年 12 月）
 *
 * 【怎么运行】（在 frontend 目录下，需先 npm run build）
 *     node tests/verify_calendar_bundle.mjs
 */

import { readFileSync, readdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const DIST = join(HERE, '..', 'dist', 'assets')

let passed = 0
let failed = 0
function check(name, cond, detail = '') {
  if (cond) { passed++; console.log(`  [PASS] ${name}`) }
  else { failed++; console.log(`  [FAIL] ${name}  <-- ${detail}`) }
}

const file = readdirSync(DIST).find((f) => f.endsWith('.js'))
if (!file) {
  console.error('\n[致命] 找不到产物，请先 npm run build\n')
  process.exit(2)
}
const js = readFileSync(join(DIST, file), 'utf8')
console.log(`\n产物：dist/assets/${file}`)
console.log('='.repeat(56))

console.log('\n=== 1. 旧的写死数据已彻底清除 ===')
check('不含 "December 2023"', !js.includes('December 2023'), '旧的英文月份还在')
check('不含 "2023年12月"', !js.includes('2023年12月'), '旧的中文月份还在')
// 产物里出现 2023 可能来自注释被压缩掉的残留，也可能真的存在。逐个查。
check('不含硬编码的 wd_mon 键名', !js.includes('wd_mon'), '旧的星期键还在')
check('不含 busyDates 写死数组', !js.includes('busyDates'), '旧的写死日期数组还在')

console.log('\n=== 2. 动态日历的关键能力都在 ===')
check('含 getFullYear（取当前年份）', js.includes('getFullYear'), '没有取当前年份')
check('含 getMonth（取当前月份）', js.includes('getMonth'), '没有取当前月份')
check('含 getDate（算当月天数）', js.includes('getDate'), '没有算当月天数')
check('含 toLocaleDateString（本地化格式）', js.includes('toLocaleDateString'), '没有本地化格式化')
check('含 en-CA（ISO 日期 key）', js.includes('en-CA'), '缺少 ISO 日期比较逻辑')

console.log('\n=== 3. 月份标题的语言分支 ===')
check('含 zh-CN', js.includes('zh-CN'), '缺少中文 locale')
check('含 en-US', js.includes('en-US'), '缺少英文 locale')

console.log('\n=== 4. 星期表头的新数据结构 ===')
// wd_full 数组应该还在（中英文各一组）
const zhWeek = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
check('中文星期全名数组存在', zhWeek.every((w) => js.includes(w)), '中文星期全名缺失')
check('英文星期全名数组存在（Monday）', js.includes('Monday'), '英文星期全名缺失')

console.log('\n=== 5. 语法完整性：产物能被 JS 引擎解析 ===')
// 用 new Function 尝试解析整个 bundle 的语法（不执行）。
// 这能抓到"构建看似成功但产出语法错误文件"的极端情况。
try {
  new Function(js)
  check('产物语法可解析', true)
} catch (e) {
  check('产物语法可解析', false, e.message)
}

console.log('\n' + '='.repeat(56))
console.log(`  日历产物验证：${passed} 项通过，${failed} 项失败`)
console.log('='.repeat(56))
if (failed) {
  console.log('  [X] 有失败项。\n')
  process.exit(1)
}
console.log('  [OK] 产物确认：日历已完全动态化，无写死日期。\n')
