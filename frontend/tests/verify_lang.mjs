/**
 * 产物验证脚本 —— 确认"中文为主、可切英文"真的打进了构建产物
 *
 * 【怎么运行】（在 frontend 目录下，需先 npm run build）
 *     node tests/verify_lang.mjs
 *
 * 【为什么要验证"产物"而不是"源码"】
 *   源码写对了不等于产物对 —— 中间还有一道构建/压缩。
 *   压缩器会做常量折叠、变量重命名、tree-shaking（摇掉没用的代码），
 *   任何一步都可能让代码行为发生变化。
 *   所以"改完 → 构建 → 验证产物"才是完整流程。
 *   企业里这一步叫"构建产物验证"，是 CI 流水线的一部分。
 *
 * 【为什么用 node 而不是 PowerShell 跑这个检查】
 *   JS 产物里大量使用反引号做字符串定界，在 PowerShell 里写正则要层层转义，
 *   极易出错（本次已经踩了两次）。用 node 读 JS 是完全不用转义的。
 *   —— 工具选对了，事情就简单一半。这是很实在的经验。
 */

import { readFileSync, readdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const DIST = join(HERE, '..', 'dist', 'assets')

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

// --- 找到构建产物 ---
let file
try {
  file = readdirSync(DIST).find((f) => f.endsWith('.js'))
} catch {
  console.error(`\n[致命] 找不到 dist/assets 目录。请先运行：npm run build\n`)
  process.exit(2)
}
if (!file) {
  console.error('\n[致命] dist/assets 里没有 .js 文件，请先运行：npm run build\n')
  process.exit(2)
}

const js = readFileSync(join(DIST, file), 'utf8')
console.log(`\n产物文件：dist/assets/${file}（${js.length} 字符）`)
console.log('='.repeat(56))

console.log('\n=== 1. 默认语言常量是 zh ===')
// 压缩后形如： Ms=`zh`
const defaultLangMatches = [...js.matchAll(/([A-Za-z_$][\w$]*)\s*=\s*`zh`/g)]
check(
  '存在 "某常量 = `zh`" 的赋值',
  defaultLangMatches.length > 0,
  '没找到，可能默认语言不是 zh，或压缩方式变了'
)
if (defaultLangMatches.length > 0) {
  const constName = defaultLangMatches[0][1]
  console.log(`        常量名（压缩后）：${constName} = \`zh\``)

  // ★ 关键一步：确认这个常量真的被用作了 lang 的 ref 初始值
  //   压缩后形如： n = H(Ms)   其中 H 是 Vue 的 ref
  const refPattern = new RegExp(`=\\s*[A-Za-z_$][\\w$]*\\(\\s*${constName}\\s*\\)`)
  check(
    `该常量被用作 ref() 的初始值（即 lang 默认为中文）`,
    refPattern.test(js),
    `未找到 ref(${constName}) 形式`
  )
}

console.log('\n=== 2. 语言切换表仍在（未被 tree-shaking 摇掉）===')
check('含语言数组 [`zh`,`en`]', /\[`zh`\s*,\s*`en`\]/.test(js), '数组被摇掉了')
check('含按钮标签 "中文"', js.includes('中文'), '缺少中文标签')
check('含按钮标签 "English"', js.includes('English'), '缺少英文标签')

console.log('\n=== 3. 切换按钮绑定正确 ===')
// 按钮会渲染 nextLangLabel() 的返回值，压缩后形如 Q(`button`,{class:`lang-btn`,onClick:i},N(xx()),1)
const btnIdx = js.indexOf('lang-btn')
check('存在 lang-btn 按钮', btnIdx >= 0, '未找到按钮')
if (btnIdx >= 0) {
  const segment = js.slice(btnIdx, btnIdx + 220)
  console.log(`        上下文：${segment.replace(/\s+/g, ' ').slice(0, 170)}`)
  check('按钮绑定了点击事件', segment.includes('onClick'), '按钮没有绑定点击事件')
}

console.log('\n=== 4. 两套词典都完整 ===')
check('中文文案「已完成」在产物中', js.includes('已完成'), '缺少中文文案')
check('英文文案 "No plans yet" 在产物中', js.includes('No plans yet'), '缺少英文文案')
check('中文文案「还没有任何计划」在产物中', js.includes('还没有任何计划'), '缺少中文空状态')

console.log('\n' + '='.repeat(56))
console.log(`  产物语言验证：${passed} 项通过，${failed} 项失败`)
console.log('='.repeat(56))
if (failed) {
  console.log('  [X] 有失败项。请检查 App.vue 的语言相关代码，然后重新构建。\n')
  process.exit(1)
}
console.log('  [OK] 产物确认：中文为默认语言，可切换英文。\n')
