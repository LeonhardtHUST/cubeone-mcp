#!/usr/bin/env bash
# =============================================================================
# cubeone-mcp / scripts/regen.sh
#
# 「备份 .ioc → 前置检查 → CubeMX 生成 → 生成核验 → 失败回滚」封装。
#
# 为什么需要这层封装
# ------------------
# CubeMX 对 .ioc 的错误是**静默非致命**的（调研报告 C2、模板 D5、HAL-PITFALLS H-6）：
# 信号名写错 / 参数没进 IPParameters 白名单，`project generate` 依然返回"成功"，
# 外设被静默丢弃。更糟的是 CubeMX **退出码恒为 0**（脚本层回 KO 也返回 0，D25），
# 所以"退出码 0"根本不是成功判据。
# 本脚本的判据是两条：① 日志里没有整行 KO；② 核验器 verdict=pass。
# 任何一步不过，都用**生成前备份**恢复 .ioc / .mxproject，绝不把未核验的配置留在工作区。
#
# 用法
# ----
#   scripts/regen.sh <工程目录> [选项]
#
# =============================================================================
set -uo pipefail

# Git Bash 下 PATH 常缺 coreutils（timeout/find/sed/…），统一补齐。
# ⚠️ 本机便利项，**他机无害可删**：这一行只把某个人的 PortableGit 路径前置，路径不存在时
#    export 一个不存在的目录不会报错，脚本照常用系统 PATH 里的同名工具。
#    已知边界：macOS 的 BSD `sort` 没有 `-V`（版本排序），`version_lt()` 在那里会静默判错
#    ⇒ 本脚本按 Git Bash / GNU coreutils 设计，macOS 未验证（不要读成"跨平台"）。
export PATH="/c/Users/Leon/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/Leon/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON="${PYTHON:-python}"

DEFAULT_JAVA="${ST_CUBEMX_JRE:-C:/ST/STM32CubeMX/jre/bin/java.exe}"
DEFAULT_CUBE="${ST_CUBEMX_EXE:-C:/ST/STM32CubeMX/STM32CubeMX.exe}"
MIN_TIMEOUT=240
#: 本机锁定的 CubeMX 基线版本（决策 D1）。只用于版本戳/迁移提示，不阻塞。
EXPECTED_CUBEMX_VERSION="${EXPECTED_CUBEMX_VERSION:-6.18.1}"

PROJECT_DIR=""
EXPECT=""
GEN_LOG=""
MX_SCRIPT=""
MAIN_C=""
MXPROJECT=""
OUT_DIR="${TMPDIR:-/tmp}/platform32-regen"
JAVA_BIN="${DEFAULT_JAVA}"
CUBE_BIN="${DEFAULT_CUBE}"
TIMEOUT_SEC=300
SKIP_GENERATE=0
DRY_RUN=0
REQUIRE_CLEAN=0
DEFAULT_ALLOW=1
ALLOW_SIGNALS=()
EXPECT_PINS=()   # --expect-pins PIN=SIGNAL（可重复），透传给核验器

log_info() { printf '[regen] %s\n' "$*" >&2; }
log_warn() { printf '[regen][warn] %s\n' "$*" >&2; }
log_err()  { printf '[regen][error] %s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
cubeone-mcp / scripts/regen.sh —— 备份 → 前置检查 → CubeMX 生成 → 核验 → 失败回滚

用法：
  scripts/regen.sh <工程目录> [选项]

选项：
  -e, --expect <list>        期望外设清单（如 GPIO,TIM4,USART2）
                             默认：从 .ioc 的 Mcu.IP* 推导（滤掉 NVIC/RCC/SYS）+ 补 GPIO
  -l, --log <path>           CubeMX 生成日志路径（默认 <out>/cubemx-generate.log）
  -m, --mx <script.mx>       CubeMX 脚本（默认 <工程>/scripts/cubemx-generate.mx）
  -o, --out <dir>            证据输出目录（默认 ${TMPDIR:-/tmp}/platform32-regen）
      --main-c <path>        覆盖 main.c 路径（默认 <工程>/Core/Src/main.c）
      --mxproject <path>     覆盖 .mxproject 路径（默认 <工程>/.mxproject）
      --java <path>          java 可执行（默认 $ST_CUBEMX_JRE 或 C:/ST/STM32CubeMX/jre/bin/java.exe）
      --cube <path>          CubeMX 可执行（默认 $ST_CUBEMX_EXE 或 C:/ST/STM32CubeMX/STM32CubeMX.exe）
      --timeout <sec>        生成超时，最小 240（默认 300；单次生成实测约 60s）
      --expect-pins <PIN=SIGNAL>  期望引脚（可重复/可逗号分隔，如 PB0=GPIO_Output），
                             透传给核验器的引脚级检查 pins_present
      --allow-signal <sig>   传给核验器的 Cannot map 白名单（默认已含 VP_RIF_VS_RIF1，D8）
      --no-default-allow     不预置 D8 白名单
      --require-clean        .ioc 有未提交内容改动时直接退出 2（默认**允许**脏，失败从备份恢复）
      --skip-generate        跳过生成，只做备份 + 核验（重跑核验用）
      --dry-run              只打印将执行的命令，不落盘、不宣称通过
  -h, --help

退出码：
  0 = 生成 + 核验全部通过（允许 warning，如 D9 的 syscalls/sysmem 叠加路径）
  1 = 跑过了但错了（生成阶段失败 / 核验 fail），**已从备份回滚**
  2 = 压根没跑（参数/IO/环境错误，或缺 .mx、--require-clean 命中脏 .ioc）

约定：
  * 不做**配置类**文本注入：改引脚/外设/参数一律走 CubeMX CLI（set 命令）或 MCP。
  * 不修改 ProjectManager.AskForMigrate：它是 CubeMX 的弹窗开关，`config save`/`saveas`
    之后的稳态，纯 `project generate` 不写回。仅当「.ioc 版本低于本机 + 值为 true」
    时打一条 warn（真实迁移需求），**不拦、不改**。
  * CubeMX 的 cwd 必须是工程根：.mx 里 `config load` 用的是相对 .ioc 路径，
    而 CubeMX 默认 cwd 是安装目录。脚本在子 shell 里 cd 进工程根并断言。
  * 失败回滚从**备份**恢复（.ioc.bak / .mxproject.bak），不是 git checkout ——
    因为默认允许 .ioc 处于未提交改动，git checkout 会抹掉用户正在验证的编辑。
  * `Core/**` 不自动回滚（局部回滚更容易看清"生成动了什么"），失败时只打印其 git 状态。
USAGE
}

die() {
  local code="$1"; shift
  log_err "$*"
  exit "$code"
}

# 版本比较：$1 < $2 ?（用 sort -V，coreutils 已在上方 PATH 中）
version_lt() {
  [ -n "$1" ] && [ -n "$2" ] && [ "$1" != "$2" ] \
    && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n 1)" = "$1" ]
}

# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------
while [ "$#" -gt 0 ]; do
  case "$1" in
    -e|--expect)        EXPECT="${2:-}"; shift 2 ;;
    -l|--log)           GEN_LOG="${2:-}"; shift 2 ;;
    -m|--mx)            MX_SCRIPT="${2:-}"; shift 2 ;;
    -o|--out)           OUT_DIR="${2:-}"; shift 2 ;;
    --main-c)           MAIN_C="${2:-}"; shift 2 ;;
    --mxproject)        MXPROJECT="${2:-}"; shift 2 ;;
    --java)             JAVA_BIN="${2:-}"; shift 2 ;;
    --cube)             CUBE_BIN="${2:-}"; shift 2 ;;
    --timeout)          TIMEOUT_SEC="${2:-}"; shift 2 ;;
    --allow-signal)     ALLOW_SIGNALS+=("${2:-}"); shift 2 ;;
    --expect-pins)      EXPECT_PINS+=("${2:-}"); shift 2 ;;
    --no-default-allow) DEFAULT_ALLOW=0; shift ;;
    --require-clean)    REQUIRE_CLEAN=1; shift ;;
    --skip-generate)    SKIP_GENERATE=1; shift ;;
    --dry-run)          DRY_RUN=1; shift ;;
    -h|--help)          usage; exit 0 ;;
    -*)                 die 2 "未知选项：$1（--help 看用法）" ;;
    *)
      if [ -z "$PROJECT_DIR" ]; then PROJECT_DIR="$1"; shift
      else die 2 "多余的参数：$1（工程目录只接受一个）"; fi ;;
  esac
done

[ -n "$PROJECT_DIR" ] || die 2 "缺少工程目录参数（--help 看用法）"
[ -d "$PROJECT_DIR" ] || die 2 "工程目录不存在：$PROJECT_DIR"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd -P)"

command -v "$PYTHON" >/dev/null 2>&1 || die 2 "找不到 python 解释器：$PYTHON（可用 PYTHON=... 覆盖）"

case "$TIMEOUT_SEC" in
  ''|*[!0-9]*) die 2 "--timeout 必须是整数秒：$TIMEOUT_SEC" ;;
esac
if [ "$TIMEOUT_SEC" -lt "$MIN_TIMEOUT" ]; then
  log_warn "--timeout ${TIMEOUT_SEC}s 过小，已提升到 ${MIN_TIMEOUT}s（CubeMX 单次生成约 60s，勿低于此值）"
  TIMEOUT_SEC="$MIN_TIMEOUT"
fi

if [ "$DEFAULT_ALLOW" -eq 1 ]; then
  # set -u 下空数组展开要写法保护（老 bash 会报 unbound variable）。
  ALLOW_SIGNALS=("VP_RIF_VS_RIF1" ${ALLOW_SIGNALS[@]+"${ALLOW_SIGNALS[@]}"})
fi

# 去重（用户可能把默认的 D8 噪音又显式传一遍），保证证据里的命令干净。
DEDUPED_SIGNALS=()
for _sig in ${ALLOW_SIGNALS[@]+"${ALLOW_SIGNALS[@]}"}; do
  [ -n "$_sig" ] || continue
  _dup=0
  for _kept in ${DEDUPED_SIGNALS[@]+"${DEDUPED_SIGNALS[@]}"}; do
    if [ "$_kept" = "$_sig" ]; then _dup=1; break; fi
  done
  [ "$_dup" -eq 0 ] && DEDUPED_SIGNALS+=("$_sig")
done
ALLOW_SIGNALS=(${DEDUPED_SIGNALS[@]+"${DEDUPED_SIGNALS[@]}"})
ALLOW_DISPLAY="（空：任何 Cannot map 都会 fail）"
[ "${#ALLOW_SIGNALS[@]}" -gt 0 ] && ALLOW_DISPLAY="${ALLOW_SIGNALS[*]}"

# ---------------------------------------------------------------------------
# 前置检查：.ioc / .mxproject / main.c / .mx 脚本 / git 状态
# ---------------------------------------------------------------------------
IOC_FILES=()
while IFS= read -r line; do
  [ -n "$line" ] && IOC_FILES+=("$line")
done < <(find "$PROJECT_DIR" -maxdepth 1 -name '*.ioc' -type f | sort)
[ "${#IOC_FILES[@]}" -gt 0 ] || die 2 "工程目录下没有 .ioc：$PROJECT_DIR"
#: 主 .ioc（工程范式里只会有一个；多 .ioc 时取字典序第一个）
IOC_FILE="${IOC_FILES[0]}"
IOC_BAK="${IOC_FILE}.bak"
MXPROJECT_BAK="${PROJECT_DIR}/.mxproject.bak"

[ -n "$MAIN_C" ] || MAIN_C="${PROJECT_DIR}/Core/Src/main.c"
[ -n "$MXPROJECT" ] || MXPROJECT="${PROJECT_DIR}/.mxproject"
[ -f "$MAIN_C" ] || die 2 "缺少生成物 main.c：$MAIN_C（先生成一次再核验；用 --main-c 覆盖）"
[ -f "$MXPROJECT" ] || die 2 "缺少 .mxproject：$MXPROJECT（先生成一次再核验；用 --mxproject 覆盖）"

if [ -z "$MX_SCRIPT" ]; then
  if [ -f "${PROJECT_DIR}/scripts/cubemx-generate.mx" ]; then
    MX_SCRIPT="${PROJECT_DIR}/scripts/cubemx-generate.mx"
  else
    MX_SCRIPT="$(find "${PROJECT_DIR}/scripts" -maxdepth 1 -name '*.mx' -type f 2>/dev/null | sort | head -n 1)"
  fi
fi
[ -n "$MX_SCRIPT" ] || die 2 "找不到 CubeMX 脚本（默认找 <工程>/scripts/cubemx-generate.mx）；用 --mx 指定"
[ -f "$MX_SCRIPT" ] || die 2 "CubeMX 脚本不存在：$MX_SCRIPT"

# ---- git：默认允许脏 .ioc（失败从备份恢复），--require-clean 才严格 ----
IN_GIT=0
DIRTY_IOC=""
if ( cd "$PROJECT_DIR" && git rev-parse --is-inside-work-tree ) >/dev/null 2>&1; then
  IN_GIT=1
  # 用 `git diff HEAD --name-only` 而不是 `git status --porcelain`：
  # status 按工作区字节判脏，CubeMX 把 .ioc 写成 CRLF 会产生"内容没变但判脏"的假阳性
  # （实测 i/lf w/crlf）；diff 会应用 .gitattributes 的 text=auto eol=lf 归一化。
  DIRTY_IOC="$( cd "$PROJECT_DIR" && git diff HEAD --name-only -- '*.ioc' 2>/dev/null )"
  if [ -n "$DIRTY_IOC" ]; then
    if [ "$REQUIRE_CLEAN" -eq 1 ]; then
      log_err "--require-clean 命中：以下 .ioc 有未提交的内容改动："
      printf '%s\n' "$DIRTY_IOC" >&2
      die 2 "先提交/stash 再跑，或去掉 --require-clean（默认允许脏，失败从备份恢复）"
    fi
    log_warn ".ioc 有未提交的内容改动（行尾差异不算），将按现状生成："
    printf '%s\n' "$DIRTY_IOC" | sed 's/^/    /' >&2
    log_warn "备份将存到 ${IOC_BAK}；**失败时从备份恢复，不用 git checkout**，不会丢你的编辑"
  fi
else
  log_warn "工程不在 git 仓库内：回滚退化为 .ioc.bak，且无法报告 Core/ 的改动"
fi

# ---- 版本戳 / 迁移提示：只读，不拦、不改 ----
IOC_VERSION="$(grep -m1 -E '^MxCube\.Version=' "$IOC_FILE" 2>/dev/null | sed -E 's/^MxCube\.Version=//' | tr -d '\r')"
IOC_MIGRATE="$(grep -m1 -E '^ProjectManager\.AskForMigrate=' "$IOC_FILE" 2>/dev/null | sed -E 's/^ProjectManager\.AskForMigrate=//' | tr -d '\r')"
if [ -n "$IOC_VERSION" ] && [ "$IOC_VERSION" != "$EXPECTED_CUBEMX_VERSION" ]; then
  log_warn ".ioc 版本戳 MxCube.Version=${IOC_VERSION} ≠ 锁定版本 ${EXPECTED_CUBEMX_VERSION}（P2）："
  log_warn "  重新生成会把 .ioc 重写成新版本格式（本机实测 619 增/106 删），建议拆独立提交。"
fi
if [ "$IOC_MIGRATE" = "true" ] && version_lt "$IOC_VERSION" "$EXPECTED_CUBEMX_VERSION"; then
  log_warn "AskForMigrate=true 且 .ioc 由旧版 CubeMX（${IOC_VERSION} < ${EXPECTED_CUBEMX_VERSION}）生成："
  log_warn "  存在真实迁移需求，-q 非交互生成**可能**停在迁移对话框。"
  log_warn "  注：本机多次实跑（含 .ioc 为 true 的稳态）均未卡死，**无实测卡死证据**；仅作提示，不拦不改。"
fi

# 期望外设：默认从 .ioc 的 Mcu.IP* 推导，滤掉 NVIC/RCC/SYS，再补 GPIO。
if [ -z "$EXPECT" ]; then
  IP_LIST="$(grep -hE '^Mcu\.IP[0-9]+=' "${IOC_FILES[@]}" 2>/dev/null \
    | sed -E 's/^Mcu\.IP[0-9]+=//' | tr -d '\r' \
    | grep -vE '^(NVIC|RCC|SYS|DBGMCU)$' | sort -u | paste -sd, -)"
  EXPECT="GPIO${IP_LIST:+,${IP_LIST}}"
  log_info "未指定 --expect，按 .ioc 推导：${EXPECT}"
fi

mkdir -p "$OUT_DIR" || die 2 "无法创建输出目录：$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
[ -n "$GEN_LOG" ] || GEN_LOG="${OUT_DIR}/cubemx-generate.log"
VERIFY_JSON="${OUT_DIR}/verify.json"
VERIFY_MD="${OUT_DIR}/verify.md"
BACKUP_JSON="${OUT_DIR}/ioc-backup.json"

log_info "工程：${PROJECT_DIR}"
log_info "期望外设：${EXPECT}"
log_info "证据输出：${OUT_DIR}"
log_info "生效 allowlist：${ALLOW_DISPLAY}（同时写进 verify.json 的 inputs.effective_allow_signals）"
if [ "${#EXPECT_PINS[@]}" -gt 0 ]; then
  log_info "期望引脚（${#EXPECT_PINS[@]} 项）：${EXPECT_PINS[*]}"
else
  log_info "期望引脚：未指定（pins_present 将 skip；引脚级改动无法由核验器保证）"
fi

# ---------------------------------------------------------------------------
# 回滚：优先从备份恢复（默认允许脏 .ioc，git checkout 会抹掉用户编辑）
# ---------------------------------------------------------------------------
rollback_project() {
  log_warn "开始回滚到生成前状态（从备份恢复，不动 git 历史）..."
  # ioc_backup.py --restore 的退出码 2 有两种含义：参数/IO 错误，或**备份完整性校验失败**
  # （.ioc.bak 与旁路摘要 .ioc.bak.sha256 不一致 → 拒绝还原、.ioc 不动）。
  # 这里不区分、只判"非 0 即失败"，因为两者的正确续作相同：都别信备份，改用 git。
  # 差异只体现在 stderr 的 [ioc_backup][integrity] 标记上，人读日志时据此定位。
  if "$PYTHON" "${SCRIPT_DIR}/ioc_backup.py" --project "$PROJECT_DIR" --restore >&2; then
    log_info "已从 ${IOC_BAK} 恢复 .ioc"
  else
    log_warn "没有 .ioc.bak 可恢复，退化为 git checkout"
    ( cd "$PROJECT_DIR" && git checkout -- '*.ioc' ) 2>/dev/null \
      && log_info "已 git checkout -- '*.ioc'" \
      || log_warn "git checkout 也失败；请人工检查 ${IOC_FILE}"
  fi
  if [ -f "$MXPROJECT_BAK" ]; then
    cp -p "$MXPROJECT_BAK" "$MXPROJECT" 2>/dev/null \
      && log_info "已从 ${MXPROJECT_BAK} 恢复 .mxproject" \
      || log_warn "恢复 .mxproject 失败"
  fi
  if [ "$IN_GIT" -eq 1 ]; then
    log_warn "Core/ 未自动回滚（局部回滚更容易看清生成动了什么）。当前状态："
    ( cd "$PROJECT_DIR" && git status --porcelain -- Core/ ) >&2 || true
    log_warn "如需丢弃本次生成产物：git -C \"$PROJECT_DIR\" checkout -- Core/"
  fi
}

# ---------------------------------------------------------------------------
# 步骤 1：备份 .ioc 与 .mxproject
# ---------------------------------------------------------------------------
run_backup() {
  log_info "步骤 1/4：备份 .ioc → .ioc.bak、.mxproject → .mxproject.bak"
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  (dry-run) %s %s --project %s --json-out %s\n' \
      "$PYTHON" "${SCRIPT_DIR}/ioc_backup.py" "$PROJECT_DIR" "$BACKUP_JSON"
    return 0
  fi
  "$PYTHON" "${SCRIPT_DIR}/ioc_backup.py" --project "$PROJECT_DIR" --json-out "$BACKUP_JSON" >&2 || return 1
  if [ -f "$MXPROJECT" ]; then
    cp -p "$MXPROJECT" "$MXPROJECT_BAK" || return 1
    log_info ".mxproject 备份：${MXPROJECT_BAK}"
  fi
  return 0
}

# ---------------------------------------------------------------------------
# 步骤 2：CubeMX 生成
# ---------------------------------------------------------------------------
run_generate() {
  log_info "步骤 2/4：CubeMX 无头生成（timeout ${TIMEOUT_SEC}s，日志 ${GEN_LOG}）"
  [ -f "$JAVA_BIN" ] || die 2 "找不到 java：$JAVA_BIN（用 --java 或 ST_CUBEMX_JRE 覆盖）"
  [ -f "$CUBE_BIN" ] || die 2 "找不到 CubeMX：$CUBE_BIN（用 --cube 或 ST_CUBEMX_EXE 覆盖）"

  local -a cmd
  if command -v timeout >/dev/null 2>&1; then
    cmd=(timeout "$TIMEOUT_SEC" "$JAVA_BIN" -jar "$CUBE_BIN" -q "$MX_SCRIPT")
  else
    log_warn "找不到 timeout 命令，退化为无超时执行（注意可能长时间挂住）"
    cmd=("$JAVA_BIN" -jar "$CUBE_BIN" -q "$MX_SCRIPT")
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  (dry-run) cd %s && %s > %s 2>&1\n' "$PROJECT_DIR" "${cmd[*]}" "$GEN_LOG"
    return 0
  fi

  # 前置不变量：CubeMX 的 cwd 必须是工程根 —— .mx 里 `config load <相对 .ioc>`，
  # 而 CubeMX 默认 cwd 是安装目录，cwd 不对就会去 C:\ST\STM32CubeMX\ 下找死 .ioc。
  local cwd_now
  cwd_now="$( cd "$PROJECT_DIR" && pwd -P )" || die 2 "无法进入工程目录：$PROJECT_DIR"
  [ "$cwd_now" = "$PROJECT_DIR" ] || die 2 "工程根解析不一致（$cwd_now ≠ $PROJECT_DIR），拒绝生成"
  log_info "CubeMX 工作目录：${cwd_now}（.mx 里的相对 .ioc 依赖此 cwd）"

  ( cd "$PROJECT_DIR" && "${cmd[@]}" ) >"$GEN_LOG" 2>&1
  return $?
}

#: CubeMX 退出码恒为 0（D25：脚本层回 KO 也返回 0），所以必须查日志里的整行 KO。
count_generate_ko() {
  local count
  count="$(grep -cE '^[[:space:]]*KO[[:space:]]*$' "$GEN_LOG" 2>/dev/null || true)"
  printf '%s' "${count:-0}" | tr -d '\r'
}

# ---------------------------------------------------------------------------
# 步骤 3：生成核验
# ---------------------------------------------------------------------------
run_verify() {
  log_info "步骤 3/4：生成核验（expect=${EXPECT}，allowlist=${ALLOW_DISPLAY}）"
  local -a args=(
    --log "$GEN_LOG"
    --main-c "$MAIN_C"
    --mxproject "$MXPROJECT"
    --ioc "$IOC_FILE"
    --expect "$EXPECT"
    --project-root "$PROJECT_DIR"
    --json-out "$VERIFY_JSON"
    --report-md "$VERIFY_MD"
  )
  local sig pin
  for sig in ${ALLOW_SIGNALS[@]+"${ALLOW_SIGNALS[@]}"}; do
    [ -n "$sig" ] && args+=(--allow-signal "$sig")
  done
  for pin in ${EXPECT_PINS[@]+"${EXPECT_PINS[@]}"}; do
    [ -n "$pin" ] && args+=(--expect-pins "$pin")
  done

  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  (dry-run) %s %s %s\n' "$PYTHON" "${SCRIPT_DIR}/verify_generation.py" "${args[*]}"
    return 0
  fi
  "$PYTHON" "${SCRIPT_DIR}/verify_generation.py" "${args[@]}"
  return $?
}

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
run_backup || die 2 "备份 .ioc 失败，未做任何改动"

if [ "$SKIP_GENERATE" -eq 1 ]; then
  log_warn "--skip-generate：跳过 CubeMX 生成，仅核验现有生成物"
else
  run_generate
  GEN_RC=$?          # 先存再判，避免中间命令覆盖 $?
  if [ "$GEN_RC" -ne 0 ]; then
    log_err "[regen] 生成阶段失败：CubeMX 退出码 ${GEN_RC}（进程级失败，如超时/崩溃）"
    rollback_project
    die 1 "生成阶段失败，已回滚。日志：${GEN_LOG}"
  fi
  if [ "$DRY_RUN" -eq 0 ]; then
    KO_COUNT="$(count_generate_ko)"
    if [ "${KO_COUNT:-0}" -gt 0 ]; then
      log_err "[regen] 生成阶段失败：日志里有 ${KO_COUNT} 行 KO（脚本层被 CubeMX 拒绝）"
      log_err "  注意：CubeMX 的**退出码是 0**，只有查日志才能发现这类失败（D25）。"
      rollback_project
      die 1 "生成阶段失败（KO），已回滚。日志：${GEN_LOG}"
    fi
    log_info "生成阶段：退出码 0 且无 KO。**无 KO 只是必要条件，不是成功证明** ——"
    log_info "  'set ip parameters' 这类命令会回 OK、无 KO，却静默空操作；最终以核验为准。"
  fi
fi

run_verify
VERIFY_RC=$?
if [ "$VERIFY_RC" -ne 0 ]; then
  log_err "[regen] 核验阶段失败（退出码 ${VERIFY_RC}）：生成跑完了，但产物不对"
  log_err "  → 外设可能被静默丢弃、路径不可复现，或输入参数有误；先看 ${VERIFY_JSON}"
  rollback_project
  exit "$VERIFY_RC"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  printf '\n[regen] (dry-run) 未执行生成与核验，不做通过判定\n'
  exit 0
fi

cat <<EOF

[regen] 全部通过 ✅
  生成日志   : ${GEN_LOG}
  核验 JSON  : ${VERIFY_JSON}
  核验报告   : ${VERIFY_MD}
  备份快照   : ${BACKUP_JSON}
下一步      : pio run（构建，L3）→ 需要实板再烧录（L5）；提交前按模板 AGENTS.md 写清验证等级
提醒        : 核验器只保证**外设级**（整只外设没被丢）。引脚级增量（如多加一个 PB0）
              不在 v1 核验范围，需另加断言：Mcu.PinsNb / __HAL_RCC_GPIOx_CLK_ENABLE() / HAL_GPIO_Init(GPIOx
EOF
exit 0
